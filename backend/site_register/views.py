import csv
import io
import urllib.request
from collections import defaultdict

from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied
from rest_framework import status

from site_gsheet_settings.models import SiteGSheet
from works.models import Work
from .models import TelegramLinkOTP, TelegramUserLink, WorkContractorTelegram, SupervisorInvite


def _is_admin(user):
    if not user.is_authenticated:
        return False
    if user.is_staff:
        return True
    profile = getattr(user, 'profile', None)
    return profile is not None and profile.role == 'admin'


def _fetch_input_tab(sheet_id):
    url = (
        f"https://docs.google.com/spreadsheets/d/{sheet_id}"
        f"/gviz/tq?tqx=out:csv&sheet=Input"
    )
    with urllib.request.urlopen(url, timeout=15) as r:
        return r.read().decode("utf-8")


def _parse_rows(csv_text):
    reader = csv.reader(io.StringIO(csv_text))
    rows = []
    for row in reader:
        if len(row) < 5:
            continue
        rows.append({
            "datetime":   row[0].strip(),
            "loa_number": row[1].strip(),
            "schedule":   row[2].strip(),
            "serial_no":  row[3].strip(),
            "item_desc":  row[4].strip(),
            "remark":     row[5].strip() if len(row) > 5 else "",
        })
    return rows


def _fetch_all_sheet_rows():
    """Returns (rows, sheet_errors)."""
    sheets = list(SiteGSheet.objects.filter(is_active=True))
    all_rows, errors = [], []
    for sheet in sheets:
        try:
            csv_text = _fetch_input_tab(sheet.sheet_id)
            rows = _parse_rows(csv_text)
            for r in rows:
                r["sheet_name"] = sheet.name
                r["sheet_id"]   = sheet.id
            all_rows.extend(rows)
        except Exception as e:
            errors.append({"sheet": sheet.name, "error": str(e)})
    return all_rows, errors


def _validate_entry(row, work, items_by_work):
    """Return list of warning strings for a single entry row."""
    warnings = []
    if not work:
        warnings.append("LOA number not found in system")
        return warnings
    work_items = items_by_work.get(work.id, {})
    schedules_in_work = {s for s, _ in work_items}
    sch = row["schedule"].lower()
    sn  = row["serial_no"].lower()
    if sch not in schedules_in_work:
        warnings.append(f"Schedule '{row['schedule']}' not found for this LOA")
    elif (sch, sn) not in work_items:
        warnings.append(f"Serial no '{row['serial_no']}' not found in schedule '{row['schedule']}'")
    return warnings


class SiteRegisterView(APIView):
    """
    Returns ALL works in the system.
    For each work, attaches matching sheet entries (by LOA number).
    """
    def get(self, request):
        if not request.user.is_authenticated:
            raise PermissionDenied("Authentication required.")

        # Admins see all works; consignees only see works assigned to them
        qs = Work.objects.prefetch_related("items", "mb_records").order_by("contractor_name")
        if not _is_admin(request.user):
            qs = qs.filter(hrms_id=request.user.username)

        works = list(qs)

        # Pre-build items lookup: { work_id: { (schedule.lower(), serial_no.lower()): item_dict } }
        items_by_work = defaultdict(dict)
        items_detail  = defaultdict(list)   # work_id → list of item dicts (for frontend)
        for w in works:
            for item in w.items.all():
                key = (
                    (item.schedule or "").strip().lower(),
                    (item.serial_number or "").strip().lower(),
                )
                items_by_work[w.id][key] = item
                items_detail[w.id].append({
                    "id":          item.id,
                    "schedule":    item.schedule,
                    "serial_no":   item.serial_number,
                    "item_desc":   item.item_desc,
                    "qty":         item.qty,
                    "unit":        item.unit,
                })

        works_by_loa = {w.loa_number: w for w in works if w.loa_number}

        # Fetch sheet rows
        all_rows, sheet_errors = _fetch_all_sheet_rows()

        # Index sheet rows by loa_number stripped of leading zeros
        # GSheets treats LOA numbers as integers and drops leading zeros
        rows_by_loa = defaultdict(list)
        for row in all_rows:
            normalized = row["loa_number"].lstrip("0") or "0"
            rows_by_loa[normalized].append(row)

        # Build response: one object per work
        result = []
        for work in works:
            loa      = work.loa_number or ""
            loa_key  = loa.lstrip("0") or "0"
            raw_rows = rows_by_loa.get(loa_key, [])

            entries = []
            for row in raw_rows:
                entry = dict(row)
                entry["warnings"] = _validate_entry(row, work, items_by_work)
                entries.append(entry)

            # Sort entries newest first
            entries.sort(key=lambda e: e["datetime"], reverse=True)

            warning_count = sum(1 for e in entries if e["warnings"])

            result.append({
                "work_id":         work.id,
                "loa_number":      loa,
                "contractor_name": work.contractor_name or "",
                "name_of_work":    work.name_of_work or "",
                "tender_number":   work.tender_number or "",
                "consignee":       work.consignee or "",
                "date_of_completion": work.date_of_completion or "",
                "items":           items_detail[work.id],
                "entries":         entries,
                "entry_count":     len(entries),
                "warning_count":   warning_count,
                "mb_count":        work.mb_records.count(),
            })

        return Response({
            "works":        result,
            "sheet_errors": sheet_errors,
        })


# ── Telegram linking ────────────────────────────────────────────────────────

@method_decorator(csrf_exempt, name='dispatch')
class TelegramOTPView(APIView):
    """
    GET  → return current OTP (or generate new one) + link status for logged-in user
    POST → generate a fresh OTP (invalidates previous)
    """
    def _link_status(self, user):
        link = getattr(user, 'telegram_link', None)
        if link and link.is_verified:
            return {'linked': True, 'telegram_user_id': link.telegram_user_id}
        return {'linked': False}

    def _otp_payload(self, otp):
        if not otp or otp.used:
            return None
        if otp.expires_at and otp.is_expired:
            return None
        return {
            'code':       otp.code,
            'expires_at': otp.expires_at.isoformat() if otp.expires_at else None,
        }

    def get(self, request):
        if not request.user.is_authenticated:
            return Response({'error': 'Login required.'}, status=status.HTTP_401_UNAUTHORIZED)
        link_status = self._link_status(request.user)
        otp = getattr(request.user, 'telegram_otp', None)
        return Response({**link_status, 'otp': self._otp_payload(otp)})

    def post(self, request):
        if not request.user.is_authenticated:
            return Response({'error': 'Login required.'}, status=status.HTTP_401_UNAUTHORIZED)
        otp = TelegramLinkOTP.generate_for(request.user)
        return Response({
            'otp': {
                'code':       otp.code,
                'expires_at': otp.expires_at.isoformat(),
            }
        })


@method_decorator(csrf_exempt, name='dispatch')
class TelegramUnlinkView(APIView):
    """DELETE → remove Telegram link for the logged-in user."""
    def delete(self, request):
        if not request.user.is_authenticated:
            return Response({'error': 'Login required.'}, status=status.HTTP_401_UNAUTHORIZED)
        link = getattr(request.user, 'telegram_link', None)
        if link:
            link.delete()
        TelegramLinkOTP.objects.filter(user=request.user).delete()
        return Response({'message': 'Telegram account unlinked.'})


# ── LOA Party Management (admin only) ───────────────────────────────────────

class LoaPartiesListView(APIView):
    """
    GET /api/site-register/parties/
    Returns all works with their mapped telegram parties.
    """
    def get(self, request):
        if not _is_admin(request.user):
            return Response({'error': 'Forbidden.'}, status=status.HTTP_403_FORBIDDEN)

        works = Work.objects.order_by('contractor_name', 'loa_number')
        mappings = (
            WorkContractorTelegram.objects
            .filter(is_active=True)
            .select_related('telegram_link__user', 'telegram_link__user__profile')
        )

        supervisors_by_work = {}
        for m in mappings:
            supervisors_by_work.setdefault(m.work_id, []).append({
                'mapping_id':  m.id,
                'user_id':     m.telegram_link.user.id,
                'hrms_id':     m.telegram_link.user.username,
                'name':        m.telegram_link.user.first_name,
                'designation': getattr(m.telegram_link.user, 'profile', None) and
                               m.telegram_link.user.profile.designation or '',
            })

        # Group LOAs by contractor
        from collections import OrderedDict
        contractors = OrderedDict()
        for w in works:
            key = w.contractor_name or '—'
            if key not in contractors:
                contractors[key] = []
            contractors[key].append({
                'id':            w.id,
                'loa_number':    w.loa_number or '—',
                'name_of_work':  w.name_of_work or '',
                'supervisors':   supervisors_by_work.get(w.id, []),
            })

        result = [
            {'contractor_name': name, 'loas': loas}
            for name, loas in contractors.items()
        ]
        return Response(result)


def _serialize_link(lnk):
    is_contractor = lnk.user.username.startswith('tg_')
    profile = getattr(lnk.user, 'profile', None)
    return {
        'link_id':          lnk.id,
        'user_id':          lnk.user.id,
        'hrms_id':          lnk.user.username,
        'name':             lnk.onboard_name or lnk.user.first_name or lnk.user.username,
        'designation':      lnk.onboard_designation or (profile.designation if profile else ''),
        'mobile':           lnk.onboard_mobile,
        'role':             profile.role if profile else '',
        'telegram_user_id': lnk.telegram_user_id,
        'telegram_chat_id': lnk.telegram_chat_id,
        'is_contractor':    is_contractor,
        'onboard_complete': bool(lnk.onboard_name),
    }


class LinkedUsersView(APIView):
    """
    GET  /api/site-register/linked-users/       — list all
    PATCH /api/site-register/linked-users/<id>/ — edit name/designation/mobile
    """
    def get(self, request, link_id=None):
        if not _is_admin(request.user):
            return Response({'error': 'Forbidden.'}, status=status.HTTP_403_FORBIDDEN)
        links = (
            TelegramUserLink.objects
            .filter(is_verified=True)
            .select_related('user', 'user__profile')
            .order_by('user__first_name')
        )
        return Response([_serialize_link(lnk) for lnk in links])

    def patch(self, request, link_id=None):
        if not _is_admin(request.user):
            return Response({'error': 'Forbidden.'}, status=status.HTTP_403_FORBIDDEN)
        try:
            lnk = TelegramUserLink.objects.select_related('user', 'user__profile').get(pk=link_id)
        except TelegramUserLink.DoesNotExist:
            return Response({'error': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        fields = []
        for field in ('onboard_name', 'onboard_designation', 'onboard_mobile'):
            if field in request.data:
                setattr(lnk, field, request.data[field])
                fields.append(field)
        if fields:
            lnk.save(update_fields=fields)
        return Response(_serialize_link(lnk))


@method_decorator(csrf_exempt, name='dispatch')
class LoaPartyView(APIView):
    """
    POST /api/site-register/parties/<work_id>/
    body: { link_id, role }  → add mapping
    DELETE /api/site-register/parties/<work_id>/<mapping_id>/
    → remove mapping
    """
    def post(self, request, work_id):
        if not _is_admin(request.user):
            return Response({'error': 'Forbidden.'}, status=status.HTTP_403_FORBIDDEN)

        link_id = request.data.get('link_id')
        role    = 'site_supervisor'  # only role for party mappings now

        try:
            work = Work.objects.get(pk=work_id)
        except Work.DoesNotExist:
            return Response({'error': 'Work not found.'}, status=status.HTTP_404_NOT_FOUND)

        try:
            link = TelegramUserLink.objects.get(pk=link_id, is_verified=True)
        except TelegramUserLink.DoesNotExist:
            return Response({'error': 'Linked user not found.'}, status=status.HTTP_404_NOT_FOUND)

        mapping, created = WorkContractorTelegram.objects.get_or_create(
            work=work, telegram_link=link,
            defaults={'role': role, 'is_active': True},
        )
        if not created:
            mapping.role      = role
            mapping.is_active = True
            mapping.save(update_fields=['role', 'is_active'])

        # Notify the supervisor on Telegram
        try:
            from telegram_settings.models import TelegramBotConfig
            import requests as _requests
            cfg = TelegramBotConfig.objects.first()
            if cfg and cfg.bot_token and link.telegram_chat_id:
                loa_label = work.loa_number or f'LOA #{work.pk}'
                msg = (
                    f"📋 <b>You have been assigned as Site Supervisor</b>\n\n"
                    f"<b>LOA:</b> {loa_label}\n"
                    f"<b>Work:</b> {work.name_of_work or '—'}\n"
                    f"<b>Contractor:</b> {work.contractor_name or '—'}\n\n"
                    "You will now receive site register notifications for this work."
                )
                _requests.post(
                    f"https://api.telegram.org/bot{cfg.bot_token}/sendMessage",
                    json={"chat_id": link.telegram_chat_id, "text": msg, "parse_mode": "HTML"},
                    timeout=10,
                )
        except Exception:
            pass  # never block the API response due to notification failure

        return Response({
            'mapping_id':  mapping.id,
            'role':        mapping.role,
            'user_id':     link.user.id,
            'hrms_id':     link.user.username,
            'name':        link.user.first_name,
            'designation': getattr(link.user, 'profile', None) and
                           link.user.profile.designation or '',
        }, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)

    def delete(self, request, work_id, mapping_id):
        if not _is_admin(request.user):
            return Response({'error': 'Forbidden.'}, status=status.HTTP_403_FORBIDDEN)
        try:
            mapping = WorkContractorTelegram.objects.get(pk=mapping_id, work_id=work_id)
        except WorkContractorTelegram.DoesNotExist:
            return Response({'error': 'Mapping not found.'}, status=status.HTTP_404_NOT_FOUND)
        mapping.delete()
        return Response({'message': 'Party removed.'})


@method_decorator(csrf_exempt, name='dispatch')
class SupervisorInviteView(APIView):
    """
    POST /api/site-register/supervisor-invite/
    body: { loa_ids: [1, 2, 3] }  → generate invite code for those LOAs

    GET /api/site-register/supervisor-invite/<code>/
    → check if invite was used; returns linked user info if so
    """
    def post(self, request):
        if not _is_admin(request.user):
            return Response({'error': 'Forbidden.'}, status=status.HTTP_403_FORBIDDEN)
        loa_ids = request.data.get('loa_ids', [])
        if not loa_ids:
            return Response({'error': 'loa_ids required.'}, status=status.HTTP_400_BAD_REQUEST)
        invite = SupervisorInvite.generate(loa_ids=loa_ids, created_by=request.user)
        return Response({
            'code':       invite.code,
            'expires_at': invite.expires_at.isoformat(),
        })

    def get(self, request, code):
        if not _is_admin(request.user):
            return Response({'error': 'Forbidden.'}, status=status.HTTP_403_FORBIDDEN)
        try:
            invite = SupervisorInvite.objects.get(code=code)
        except SupervisorInvite.DoesNotExist:
            return Response({'error': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

        if invite.used and invite.used_by_link:
            lnk = invite.used_by_link
            return Response({
                'used': True,
                'linked_user': {
                    'name':        lnk.user.first_name or lnk.user.username,
                    'hrms_id':     lnk.user.username,
                    'designation': getattr(lnk.user, 'profile', None) and
                                   lnk.user.profile.designation or '',
                },
            })
        return Response({'used': False})
