from collections import defaultdict

from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied
from rest_framework import status
from django.contrib.auth.models import User

from works.models import Work
from works.utils import contractor_nickname as _nickname, is_admin_user as _is_admin
from .models import (
    TelegramLinkOTP, TelegramUserLink, WorkContractorTelegram, SupervisorInvite,
    RlyTelegramLink, RlyOfficialInvite, SiteRegisterThread,
)

SR_CATEGORY_LABELS = {
    'order':               'Rly Official Order',
    'progress':            'Progress Update',
    'hindrance':           'Hindrance',
    'inspection_request':  'Inspection Request',
    'document_submission': 'Document Submission',
    'general_remark':      'General Remark',
}


def _is_consignee(user):
    if not user.is_authenticated:
        return False
    profile = getattr(user, 'profile', None)
    return profile is not None and profile.role == 'consignee'


def _consignee_owns_loas(user, loa_ids):
    """Return True if all loa_ids are assigned to this consignee (hrms_id match)."""
    if not loa_ids:
        return False
    owned = set(Work.objects.filter(pk__in=loa_ids, hrms_id=user.username).values_list('pk', flat=True))
    return owned == set(loa_ids)


def _can_access_site_register(user):
    if not user.is_authenticated:
        return False
    if user.is_staff:
        return True
    profile = getattr(user, 'profile', None)
    return profile is not None and profile.role in ('admin', 'consignee')


class SiteRegisterView(APIView):
    def get(self, request):
        if not request.user.is_authenticated:
            raise PermissionDenied("Authentication required.")
        if not _can_access_site_register(request.user):
            raise PermissionDenied("Access restricted to consignees and admins.")

        # Admins see all works. A consignee sees their own assigned work(s) in
        # full, plus any other work where they've personally authored an SR
        # entry (so an unassigned consignee still finds entries they made on
        # someone else's LOA) — thread-level filtering below then limits what
        # shows for those non-owned works to just their own entries.
        is_admin_req = _is_admin(request.user)
        qs = Work.objects.prefetch_related("items").order_by("contractor_name")
        owned_ids = None
        if not is_admin_req:
            owned_ids = set(
                Work.objects.filter(hrms_id=request.user.username).values_list('pk', flat=True)
            )
            authored_ids = set(
                SiteRegisterThread.objects.filter(created_by=request.user).values_list('work_id', flat=True)
            )
            qs = qs.filter(pk__in=owned_ids | authored_ids)

        works = list(qs)

        items_detail = defaultdict(list)
        for w in works:
            for item in w.items.all():
                items_detail[w.id].append({
                    "id":        item.id,
                    "schedule":  item.schedule,
                    "serial_no": item.serial_number,
                    "item_desc": item.item_desc,
                    "qty":       item.qty,
                    "unit":      item.unit,
                })

        # Build username→display map for consignees in one query
        usernames = [w.hrms_id for w in works if w.hrms_id]
        user_map = {}
        for u in User.objects.filter(username__in=usernames).select_related('profile'):
            name = u.first_name or u.username
            desig = getattr(getattr(u, 'profile', None), 'designation', None)
            user_map[u.username] = f"{name} ({desig})" if desig else name

        # Build response: one object per work
        result = []
        for work in works:
            loa = work.loa_number or ""
            consignee_display = user_map.get(work.hrms_id or '') or work.consignee or ''
            result.append({
                "work_id":             work.id,
                "loa_number":          loa,
                "contractor_name":     work.contractor_name or "",
                "contractor_nickname": _nickname(work.contractor_name or ""),
                "name_of_work":        work.name_of_work or "",
                "tender_number":      work.tender_number or "",
                "consignee":          consignee_display,
                "date_of_completion": work.date_of_completion or "",
                "items":              items_detail[work.id],
            })

        # Fetch all SR threads for these works, with messages
        threads_qs = (
            SiteRegisterThread.objects
            .filter(work__in=works)
            .select_related('work', 'work_item', 'created_by', 'created_by__profile')
            .prefetch_related('messages__sender__telegram_link', 'messages__sender__profile',
                              'messages__attachments')
            .order_by('created_at')
        )
        threads_by_work = defaultdict(list)
        def _derive_msg_role(m):
            if m.sender_role:
                return m.sender_role
            if not m.sender:
                return 'rly_official'
            tg = getattr(m.sender, 'telegram_link', None)
            return 'site_supervisor' if tg is not None else 'rly_official'

        def _msg_designation(m, actual_role):
            if not m.sender:
                return ''
            if actual_role == 'site_supervisor':
                tg = getattr(m.sender, 'telegram_link', None)
                return (tg.onboard_designation if tg else '') or ''
            p = getattr(m.sender, 'profile', None)
            return p.designation if p else ''

        for t in threads_qs:
            if owned_ids is not None and t.work_id not in owned_ids and t.created_by_id != request.user.id:
                continue
            all_msgs = [
                {
                    'id':                m.id,
                    'sender_role':       _derive_msg_role(m),
                    'sender_name':       (m.sender.first_name or m.sender.username) if m.sender else '—',
                    'sender_designation': _msg_designation(m, _derive_msg_role(m)),
                    'text':              m.message_text,
                    'created_at':        m.created_at.isoformat(),
                    'attachments': [
                        {
                            'id':        a.id,
                            'att_number': a.att_number,
                            'file_type': a.file_type,
                            'filename':  a.original_filename,
                        }
                        for a in m.attachments.all()
                    ],
                }
                for m in t.messages.order_by('created_at')
            ]
            ss_msgs = [m for m in all_msgs if m['sender_role'] == 'site_supervisor']
            profile = getattr(t.created_by, 'profile', None) if t.created_by else None
            if t.initiated_by_role == 'site_supervisor':
                tg_init = getattr(t.created_by, 'telegram_link', None) if t.created_by else None
                created_desig = (tg_init.onboard_designation if tg_init else '') or ''
            else:
                created_desig = (profile.designation if profile else '') or ''
            threads_by_work[t.work_id].append({
                'id':                   t.pk,
                'sr_number':            t.sr_number,
                'category':             t.category,
                'instruction_type':     'item' if t.work_item_id else 'general',
                'initial_text':         t.initial_text,
                'status':               t.status,
                'initiated_by_role':    t.initiated_by_role,
                'created_by_name':      (t.created_by.first_name or t.created_by.username) if t.created_by else '—',
                'created_by_designation': created_desig,
                'created_at':           t.created_at.isoformat(),
                'work_item_id':         t.work_item_id,
                'work_item_ref':        f"{t.work_item.schedule}-{(t.work_item.serial_number or '').strip()}" if t.work_item else None,
                'location':             t.location or '',
                'first_response':       ss_msgs[0] if ss_msgs else None,
                'response_count':       len(ss_msgs),
                'messages':             all_msgs,
            })

        # Attach thread data to each work result
        for item in result:
            item['threads']      = threads_by_work[item['work_id']]
            item['thread_count'] = len(item['threads'])

        return Response({"works": result})


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
            profile = getattr(user, 'profile', None)
            return {
                'linked': True,
                'link_info': {
                    'telegram_user_id': link.telegram_user_id,
                    'telegram_chat_id': link.telegram_chat_id,
                    'name':        user.first_name or user.username,
                    'hrms_id':     user.username,
                    'designation': profile.designation if profile else '',
                    'mobile':      link.onboard_mobile or '',
                    'in_system':   True,
                    'is_self':     True,
                },
            }
        return {'linked': False, 'link_info': None}

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

    def patch(self, request):
        """Update mobile on the logged-in user's own TelegramUserLink."""
        if not request.user.is_authenticated:
            return Response({'error': 'Login required.'}, status=status.HTTP_401_UNAUTHORIZED)
        link = getattr(request.user, 'telegram_link', None)
        if not link or not link.is_verified:
            return Response({'error': 'Not linked.'}, status=status.HTTP_404_NOT_FOUND)
        mobile = request.data.get('mobile', '').strip()
        link.onboard_mobile = mobile
        link.save(update_fields=['onboard_mobile'])
        return Response({'ok': True, 'mobile': mobile})


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
    Admin: all works. Consignee: only their assigned LOAs.
    """
    def get(self, request):
        is_admin = _is_admin(request.user)
        is_consignee = (
            not is_admin and
            request.user.is_authenticated and
            getattr(getattr(request.user, 'profile', None), 'role', None) == 'consignee'
        )
        if not is_admin and not is_consignee:
            return Response({'error': 'Forbidden.'}, status=status.HTTP_403_FORBIDDEN)

        works = Work.objects.order_by('contractor_name', 'loa_number')
        if is_consignee:
            works = works.filter(hrms_id=request.user.username)
            if not works.exists():
                return Response(
                    {'error': 'No assigned LOA — nothing to manage here.'},
                    status=status.HTTP_403_FORBIDDEN,
                )
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
    GET  /api/site-register/linked-users/?loa_ids=1,2,3  — supervisors for given LOAs
    GET  /api/site-register/linked-users/                 — all linked users
    PATCH /api/site-register/linked-users/<id>/           — edit name/designation/mobile
    DELETE /api/site-register/linked-users/<id>/          — remove supervisor mapping for given loa_ids
    """
    def get(self, request, link_id=None):
        is_admin     = _is_admin(request.user)
        is_consignee = _is_consignee(request.user)
        if not is_admin and not is_consignee:
            return Response({'error': 'Forbidden.'}, status=status.HTTP_403_FORBIDDEN)

        loa_ids_raw = request.query_params.get('loa_ids', '')
        if loa_ids_raw:
            try:
                loa_ids = [int(x) for x in loa_ids_raw.split(',') if x.strip()]
            except ValueError:
                return Response({'error': 'Invalid loa_ids.'}, status=status.HTTP_400_BAD_REQUEST)
            # Consignee can only fetch supervisors for LOAs they own
            if is_consignee and not is_admin and not _consignee_owns_loas(request.user, loa_ids):
                return Response({'error': 'Forbidden.'}, status=status.HTTP_403_FORBIDDEN)
            mappings = (
                WorkContractorTelegram.objects
                .filter(work_id__in=loa_ids, is_active=True)
                .select_related('telegram_link__user', 'telegram_link__user__profile', 'work')
                .order_by('telegram_link__onboard_name')
            )
            result = []
            for m in mappings:
                row = _serialize_link(m.telegram_link)
                row['mapping_id'] = m.pk
                row['work_id']    = m.work_id
                row['loa_number'] = m.work.loa_number or f'LOA #{m.work_id}'
                result.append(row)
            return Response(result)

        # Full list — consignees must provide loa_ids; only admins can list all
        if not is_admin:
            return Response({'error': 'loa_ids required.'}, status=status.HTTP_400_BAD_REQUEST)
        links = (
            TelegramUserLink.objects
            .filter(is_verified=True)
            .select_related('user', 'user__profile')
            .order_by('user__first_name')
        )
        return Response([_serialize_link(lnk) for lnk in links])

    def delete(self, request, link_id=None):
        if not _is_admin(request.user):
            return Response({'error': 'Forbidden.'}, status=status.HTTP_403_FORBIDDEN)
        # bulk unlink: link_id + loa_ids → deactivate all mappings for that user in those LOAs
        loa_ids_raw = request.data.get('loa_ids') or request.query_params.get('loa_ids')
        if loa_ids_raw and link_id:
            try:
                loa_ids = [int(x) for x in str(loa_ids_raw).split(',') if str(x).strip()]
            except ValueError:
                return Response({'error': 'Invalid loa_ids.'}, status=status.HTTP_400_BAD_REQUEST)
            updated = WorkContractorTelegram.objects.filter(
                telegram_link_id=link_id, work_id__in=loa_ids, is_active=True
            ).update(is_active=False)
            return Response({'ok': True, 'removed': updated})
        # single unlink by mapping_id
        mapping_id = request.data.get('mapping_id') or request.query_params.get('mapping_id')
        if not mapping_id:
            return Response({'error': 'mapping_id or (link_id + loa_ids) required.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            mapping = WorkContractorTelegram.objects.get(pk=mapping_id)
        except WorkContractorTelegram.DoesNotExist:
            return Response({'error': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        mapping.is_active = False
        mapping.save(update_fields=['is_active'])
        return Response({'ok': True})

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
        is_admin = _is_admin(request.user)
        is_consignee = _is_consignee(request.user)
        if not is_admin and not is_consignee:
            return Response({'error': 'Forbidden.'}, status=status.HTTP_403_FORBIDDEN)
        if is_consignee and not is_admin and not _consignee_owns_loas(request.user, [int(work_id)]):
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
        is_admin = _is_admin(request.user)
        is_consignee = _is_consignee(request.user)
        if not is_admin and not is_consignee:
            return Response({'error': 'Forbidden.'}, status=status.HTTP_403_FORBIDDEN)
        if is_consignee and not is_admin and not _consignee_owns_loas(request.user, [int(work_id)]):
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
        is_admin     = _is_admin(request.user)
        is_consignee = _is_consignee(request.user)
        if not is_admin and not is_consignee:
            return Response({'error': 'Forbidden.'}, status=status.HTTP_403_FORBIDDEN)
        loa_ids = request.data.get('loa_ids', [])
        if not loa_ids:
            return Response({'error': 'loa_ids required.'}, status=status.HTTP_400_BAD_REQUEST)
        # Consignee can only invite for their own LOAs
        if is_consignee and not is_admin and not _consignee_owns_loas(request.user, loa_ids):
            return Response({'error': 'Forbidden.'}, status=status.HTTP_403_FORBIDDEN)
        invite = SupervisorInvite.generate(loa_ids=loa_ids, created_by=request.user)
        return Response({
            'code':       invite.code,
            'expires_at': invite.expires_at.isoformat(),
        })

    def get(self, request, code):
        if not _is_admin(request.user) and not _is_consignee(request.user):
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


# ── Rly Official Delegate Links ─────────────────────────────────────────────

def _serialize_rly_link(lnk, include_added_by=False):
    data = {
        'id':               lnk.id,
        'hrms_id':          lnk.hrms_id,
        'name':             lnk.display_name,
        'designation':      lnk.designation,
        'mobile':           lnk.mobile,
        'telegram_user_id': lnk.telegram_user_id,
        'telegram_chat_id': lnk.telegram_chat_id,
        'is_verified':      lnk.is_verified,
        'linked_at':        lnk.linked_at.strftime('%Y-%m-%d %H:%M') if lnk.linked_at else None,
        'in_system':        lnk.system_user_id is not None,
    }
    if include_added_by:
        added_by = lnk.added_by
        data['added_by_hrms'] = added_by.username if added_by else ''
        data['added_by_name'] = added_by.first_name or added_by.username if added_by else ''
    return data


class RlyLinkedUsersView(APIView):
    """
    GET    /api/site-register/rly-linked-users/      — list delegates
                admin: all records; others: only added_by=self
    PATCH  /api/site-register/rly-linked-users/<id>/ — edit name/designation/mobile
    DELETE /api/site-register/rly-linked-users/<id>/ — unlink (hard delete)
    """
    def get(self, request):
        if not request.user.is_authenticated:
            return Response({'error': 'Login required.'}, status=status.HTTP_401_UNAUTHORIZED)
        if _is_admin(request.user):
            links = (
                RlyTelegramLink.objects
                .select_related('added_by')
                .order_by('added_by__first_name', 'name', 'linked_at')
            )
            return Response([_serialize_rly_link(lnk, include_added_by=True) for lnk in links])
        links = (
            RlyTelegramLink.objects
            .filter(added_by=request.user)
            .order_by('name', 'linked_at')
        )
        return Response([_serialize_rly_link(lnk) for lnk in links])

    def patch(self, request, link_id=None):
        if not request.user.is_authenticated:
            return Response({'error': 'Login required.'}, status=status.HTTP_401_UNAUTHORIZED)
        try:
            if _is_admin(request.user):
                lnk = RlyTelegramLink.objects.get(pk=link_id)
            else:
                lnk = RlyTelegramLink.objects.get(pk=link_id, added_by=request.user)
        except RlyTelegramLink.DoesNotExist:
            return Response({'error': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        fields = []
        for f in ('name', 'designation', 'mobile'):
            if f in request.data:
                setattr(lnk, f, request.data[f])
                fields.append(f)
        if fields:
            lnk.save(update_fields=fields)
        return Response(_serialize_rly_link(lnk))

    def delete(self, request, link_id=None):
        if not request.user.is_authenticated:
            return Response({'error': 'Login required.'}, status=status.HTTP_401_UNAUTHORIZED)
        try:
            if _is_admin(request.user):
                lnk = RlyTelegramLink.objects.get(pk=link_id)
            else:
                lnk = RlyTelegramLink.objects.get(pk=link_id, added_by=request.user)
        except RlyTelegramLink.DoesNotExist:
            return Response({'error': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        # Delete ghost user if it was created for this link (no real account)
        if lnk.ghost_user and not lnk.system_user:
            lnk.ghost_user.delete()
        lnk.delete()
        return Response({'ok': True})


@method_decorator(csrf_exempt, name='dispatch')
class RlyOfficialInviteView(APIView):
    """
    POST /api/site-register/rly-invite/          — generate invite code
    GET  /api/site-register/rly-invite/<code>/   — check if code was used
    """
    def post(self, request):
        if not request.user.is_authenticated:
            return Response({'error': 'Login required.'}, status=status.HTTP_401_UNAUTHORIZED)
        invite = RlyOfficialInvite.generate(created_by=request.user)
        return Response({
            'code':       invite.code,
            'expires_at': invite.expires_at.isoformat(),
        })

    def get(self, request, code=None):
        if not request.user.is_authenticated:
            return Response({'error': 'Login required.'}, status=status.HTTP_401_UNAUTHORIZED)
        try:
            invite = RlyOfficialInvite.objects.get(code=code, created_by=request.user)
        except RlyOfficialInvite.DoesNotExist:
            return Response({'error': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        if invite.used and invite.used_by_link:
            lnk = invite.used_by_link
            return Response({'used': True, 'linked_user': _serialize_rly_link(lnk)})
        return Response({'used': False})


class ThreadStatsView(APIView):
    """GET /api/site-register/thread-stats/?work_id=X — SR analytics for WorkDetails page."""
    def get(self, request):
        if not request.user.is_authenticated:
            raise PermissionDenied()
        work_id = request.query_params.get('work_id')
        empty = {'total': 0, 'by_category': {}, 'by_month': {}, 'by_status': {}}
        if not work_id:
            return Response(empty)
        by_category = {}
        by_month    = {}
        by_status   = {}
        qs = SiteRegisterThread.objects.filter(work_id=work_id).values('category', 'status', 'created_at')
        for t in qs:
            cat = t['category']
            by_category[cat] = by_category.get(cat, 0) + 1
            month = t['created_at'].strftime('%Y-%m')
            by_month[month] = by_month.get(month, 0) + 1
            st = t['status']
            by_status[st] = by_status.get(st, 0) + 1
        return Response({
            'total':       qs.count(),
            'by_category': by_category,
            'by_month':    dict(sorted(by_month.items())),
            'by_status':   by_status,
        })
