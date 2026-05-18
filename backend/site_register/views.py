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
from .models import TelegramLinkOTP, TelegramUserLink, WorkContractorTelegram


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

    def get(self, request):
        if not request.user.is_authenticated:
            return Response({'error': 'Login required.'}, status=status.HTTP_401_UNAUTHORIZED)
        link_status = self._link_status(request.user)
        otp = getattr(request.user, 'telegram_otp', None)
        return Response({
            **link_status,
            'otp': otp.code if otp and not otp.used else None,
        })

    def post(self, request):
        if not request.user.is_authenticated:
            return Response({'error': 'Login required.'}, status=status.HTTP_401_UNAUTHORIZED)
        otp = TelegramLinkOTP.generate_for(request.user)
        return Response({'otp': otp.code})


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

        works = Work.objects.order_by('loa_number').values(
            'id', 'loa_number', 'contractor_name', 'name_of_work'
        )
        mappings = (
            WorkContractorTelegram.objects
            .filter(is_active=True)
            .select_related('telegram_link__user', 'telegram_link__user__profile')
        )

        parties_by_work = {}
        for m in mappings:
            parties_by_work.setdefault(m.work_id, []).append({
                'mapping_id':  m.id,
                'role':        m.role,
                'user_id':     m.telegram_link.user.id,
                'hrms_id':     m.telegram_link.user.username,
                'name':        m.telegram_link.user.first_name,
                'designation': getattr(m.telegram_link.user, 'profile', None) and
                               m.telegram_link.user.profile.designation or '',
            })

        result = []
        for w in works:
            result.append({
                **w,
                'parties': parties_by_work.get(w['id'], []),
            })
        return Response(result)


class LinkedUsersView(APIView):
    """
    GET /api/site-register/linked-users/
    Returns all users who have a verified Telegram link (for party assignment dropdown).
    """
    def get(self, request):
        if not _is_admin(request.user):
            return Response({'error': 'Forbidden.'}, status=status.HTTP_403_FORBIDDEN)

        links = (
            TelegramUserLink.objects
            .filter(is_verified=True)
            .select_related('user', 'user__profile')
            .order_by('user__first_name')
        )
        return Response([
            {
                'link_id':     lnk.id,
                'user_id':     lnk.user.id,
                'hrms_id':     lnk.user.username,
                'name':        lnk.user.first_name,
                'designation': getattr(lnk.user, 'profile', None) and
                               lnk.user.profile.designation or '',
                'role':        getattr(lnk.user, 'profile', None) and
                               lnk.user.profile.role or '',
            }
            for lnk in links
        ])


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
        role    = request.data.get('role', '').strip()
        if role not in ('sse', 'contractor'):
            return Response({'error': 'role must be sse or contractor.'}, status=status.HTTP_400_BAD_REQUEST)

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
