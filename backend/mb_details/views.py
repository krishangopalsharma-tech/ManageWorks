from django.db import transaction
from django.db.models import Sum, Q
from rest_framework import status, generics
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied
from rest_framework.parsers import MultiPartParser, FormParser

from works.models import Work, WorkItem
from works.utils import contractor_nickname as _nickname
from .models import MBRecord, MBItem
from .serializers import MBRecordSerializer
from .parsers import parse_rm_pdf


def _is_admin(user):
    if not user.is_authenticated:
        return False
    if user.is_staff:
        return True
    profile = getattr(user, 'profile', None)
    return profile is not None and profile.role == 'admin'


def _check_work_access(user, work):
    """Consignee can only access works mapped to their HRMS ID."""
    if not user.is_authenticated:
        raise PermissionDenied("Authentication required.")
    if _is_admin(user):
        return
    if work.hrms_id != user.username:
        raise PermissionDenied("You are not the consignee for this work.")


def _block_admin_write(user):
    """Admins can view MB details but cannot create, edit, or delete them."""
    if _is_admin(user):
        raise PermissionDenied("Admins can view MB details but cannot create, edit, or delete them.")


class WorkSearchView(APIView):
    """GET /api/mb-details/works/?q=loa"""

    def get(self, request):
        if not request.user.is_authenticated:
            return Response({'error': 'Login required.'}, status=status.HTTP_401_UNAUTHORIZED)
        q = request.query_params.get('q', '').strip()
        qs = Work.objects.all()
        if not _is_admin(request.user):
            qs = qs.filter(hrms_id=request.user.username)
        all_works = list(qs)
        if q:
            ql = q.lower()
            qu = q.upper()
            all_works = [
                w for w in all_works
                if ql in (w.loa_number or '').lower()
                or ql in (w.tender_number or '').lower()
                or ql in (w.contractor_name or '').lower()
                or ql in (w.consignee or '').lower()
                or qu in _nickname(w.contractor_name or '')
            ]
        data = [
            {
                'id': w.id,
                'loa_number': w.loa_number or '',
                'tender_number': w.tender_number or '',
                'contractor_name': w.contractor_name or '',
                'contractor_nickname': _nickname(w.contractor_name or ''),
                'consignee': w.consignee or '',
                'name_of_work': w.name_of_work or '',
            }
            for w in all_works[:50]
        ]
        return Response(data)


class WorkItemSearchView(APIView):
    """GET /api/mb-details/works/<work_id>/items/?schedule=A|B|&q=cable"""

    def get(self, request, work_id):
        try:
            work = Work.objects.get(pk=work_id)
        except Work.DoesNotExist:
            return Response({'error': 'Work not found.'}, status=status.HTTP_404_NOT_FOUND)
        _check_work_access(request.user, work)

        schedule = (request.query_params.get('schedule') or '').strip().upper()
        q        = (request.query_params.get('q') or '').strip()

        items = WorkItem.objects.filter(work_id=work_id)
        if schedule in ('A', 'B'):
            items = items.filter(schedule__istartswith=schedule)
        if q:
            items = items.filter(
                Q(item_desc__icontains=q) |
                Q(serial_number__icontains=q)
            )

        data = [
            {
                'id':              i.id,
                'serial_number':   i.serial_number,
                'schedule':        i.schedule,
                'item_desc':       i.item_desc,
                'qty':             i.qty,
                'unit':            i.unit,
                'unit_rate_below': i.unit_rate_below,
                'total_amount':    i.total_amount,
            }
            for i in items[:200]
        ]
        return Response(data)



class MBRecordListCreateView(generics.ListCreateAPIView):
    """
    GET  /api/mb-details/records/?work_id=
    POST /api/mb-details/records/
      body: {
        work, mb_number, notes,
        items: [{ work_item, quantity, prior_percentage, current_percentage }]
      }
    """
    serializer_class = MBRecordSerializer

    def get_queryset(self):
        qs = MBRecord.objects.select_related('work', 'created_by').prefetch_related('items__work_item')
        if not _is_admin(self.request.user):
            qs = qs.filter(work__hrms_id=self.request.user.username)
        work_id = self.request.query_params.get('work_id')
        if work_id:
            qs = qs.filter(work_id=work_id)
        return qs.order_by('-created_at')

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        _block_admin_write(request.user)

        work_id   = request.data.get('work')
        mb_number = request.data.get('mb_number')
        notes     = request.data.get('notes', '') or ''
        items     = request.data.get('items') or []

        if not work_id:
            return Response({'error': 'work is required.'}, status=status.HTTP_400_BAD_REQUEST)
        mb_number = (str(mb_number) if mb_number is not None else '').strip()
        if not mb_number:
            return Response({'error': 'mb_number is required.'}, status=status.HTTP_400_BAD_REQUEST)
        if not isinstance(items, list) or not items:
            return Response({'error': 'At least one item is required.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            work = Work.objects.get(pk=work_id)
        except Work.DoesNotExist:
            return Response({'error': 'Work not found.'}, status=status.HTTP_404_NOT_FOUND)

        _check_work_access(request.user, work)

        if MBRecord.objects.filter(work=work, mb_number=mb_number).exists():
            return Response({'error': f'MB number "{mb_number}" already exists for this work.'},
                            status=status.HTTP_400_BAD_REQUEST)

        measurement_date = request.data.get('measurement_date') or None

        record = MBRecord.objects.create(
            work=work,
            mb_number=mb_number,
            measurement_date=measurement_date,
            notes=notes,
            created_by=request.user if request.user.is_authenticated else None,
        )

        for row in items:
            wi_id   = row.get('work_item')
            try:
                qty     = float(row.get('quantity') or 0)
                cur_pct = float(row.get('current_percentage') or 0)
            except (ValueError, TypeError):
                record.delete()
                return Response({'error': f'Invalid numeric values for item {wi_id}.'},
                                status=status.HTTP_400_BAD_REQUEST)

            if qty <= 0:
                continue
            if cur_pct <= 0 or cur_pct > 100:
                record.delete()
                return Response({'error': f'current_percentage must be between 0 and 100 for item {wi_id}.'},
                                status=status.HTTP_400_BAD_REQUEST)

            try:
                wi = WorkItem.objects.get(pk=wi_id, work=work)
            except WorkItem.DoesNotExist:
                record.delete()
                return Response({'error': f'Item {wi_id} not found in this work.'},
                                status=status.HTTP_404_NOT_FOUND)

            MBItem.objects.create(
                mb_record=record, work_item=wi,
                quantity=qty, current_percentage=cur_pct, amount=0,
            )

        return Response(MBRecordSerializer(record).data, status=status.HTTP_201_CREATED)


class MBRecordDetailView(generics.RetrieveDestroyAPIView):
    """GET / DELETE / PATCH /api/mb-details/records/<pk>/"""
    queryset         = MBRecord.objects.select_related('work').prefetch_related('items__work_item')
    serializer_class = MBRecordSerializer

    def perform_destroy(self, instance):
        _block_admin_write(self.request.user)
        if instance.created_by_id != self.request.user.id:
            raise PermissionDenied("Only the consignee who created this MB record can delete it.")
        instance.delete()

    @transaction.atomic
    def patch(self, request, *args, **kwargs):
        _block_admin_write(request.user)
        record = self.get_object()
        if record.created_by_id != request.user.id:
            raise PermissionDenied("Only the consignee who created this MB record can edit it.")

        mb_number        = str(request.data.get('mb_number', record.mb_number) or '').strip()
        measurement_date = request.data.get('measurement_date', record.measurement_date) or None
        notes            = request.data.get('notes', record.notes) or ''
        items_data       = request.data.get('items')

        if not mb_number:
            return Response({'error': 'mb_number is required.'}, status=status.HTTP_400_BAD_REQUEST)

        # Check uniqueness only if mb_number actually changed
        if mb_number != record.mb_number:
            if MBRecord.objects.filter(work=record.work, mb_number=mb_number).exclude(pk=record.pk).exists():
                return Response(
                    {'error': f'MB number "{mb_number}" already exists for this work.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        record.mb_number        = mb_number
        record.measurement_date = measurement_date
        record.notes            = notes
        record.save()

        if items_data is not None:
            record.items.all().delete()
            for row in items_data:
                wi_id = row.get('work_item')
                try:
                    qty     = float(row.get('quantity') or 0)
                    cur_pct = float(row.get('current_percentage') or 0)
                except (ValueError, TypeError):
                    return Response({'error': f'Invalid numeric values for item {wi_id}.'},
                                    status=status.HTTP_400_BAD_REQUEST)

                if qty <= 0:
                    continue
                if cur_pct <= 0 or cur_pct > 100:
                    return Response({'error': f'current_percentage must be between 0 and 100 for item {wi_id}.'},
                                    status=status.HTTP_400_BAD_REQUEST)

                try:
                    wi = WorkItem.objects.get(pk=wi_id, work=record.work)
                except WorkItem.DoesNotExist:
                    return Response({'error': f'Item {wi_id} not found in this work.'},
                                    status=status.HTTP_404_NOT_FOUND)

                MBItem.objects.create(
                    mb_record=record, work_item=wi,
                    quantity=qty, current_percentage=cur_pct, amount=0,
                )

        return Response(MBRecordSerializer(record).data)


class MBSummaryView(APIView):
    """
    GET /api/mb-details/summary/?work_id=
    Financial progress by schedule (via item.schedule, since MB is schedule-agnostic).
    """

    def get(self, request):
        if not request.user.is_authenticated:
            return Response({'error': 'Login required.'}, status=status.HTTP_401_UNAUTHORIZED)
        work_id = request.query_params.get('work_id')

        items_qs = WorkItem.objects.all()
        mb_qs    = MBItem.objects.all()
        if work_id:
            items_qs = items_qs.filter(work_id=work_id)
            mb_qs    = mb_qs.filter(mb_record__work_id=work_id)

        total_work_amount = items_qs.aggregate(t=Sum('total_amount'))['t'] or 0
        mb_total          = mb_qs.aggregate(t=Sum('amount'))['t'] or 0
        fin_prog          = (mb_total / total_work_amount * 100) if total_work_amount > 0 else 0

        sch_a = mb_qs.filter(work_item__schedule__istartswith='A').aggregate(t=Sum('amount'))['t'] or 0
        sch_b = mb_qs.filter(work_item__schedule__istartswith='B').aggregate(t=Sum('amount'))['t'] or 0
        a_total = items_qs.filter(schedule__istartswith='A').aggregate(t=Sum('total_amount'))['t'] or 0
        b_total = items_qs.filter(schedule__istartswith='B').aggregate(t=Sum('total_amount'))['t'] or 0

        return Response({
            'total_work_amount':  round(total_work_amount, 2),
            'mb_total':           round(mb_total, 2),
            'financial_progress': round(fin_prog, 2),
            'sch_a_billed':       round(sch_a, 2),
            'sch_b_billed':       round(sch_b, 2),
            'sch_a_total':        round(a_total, 2),
            'sch_b_total':        round(b_total, 2),
            'sch_a_pct':          round((sch_a / a_total * 100) if a_total else 0, 2),
            'sch_b_pct':          round((sch_b / b_total * 100) if b_total else 0, 2),
        })


class PDFImportView(APIView):
    """
    POST /api/mb-details/import-pdf/
      multipart fields:
        file:    the RM PDF
        work_id: target Work id

    Returns a draft (NO database writes) for the frontend to review and save.
    Warnings include: agreement mismatch, unmatched items, qty mismatch,
    and items where payment % > 0 but supply/execution has not been recorded.
    """
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        _block_admin_write(request.user)

        file_obj = request.FILES.get('file')
        work_id  = request.data.get('work_id')

        if not file_obj:
            return Response({'error': 'file is required.'}, status=status.HTTP_400_BAD_REQUEST)
        if not work_id:
            return Response({'error': 'work_id is required.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            work = Work.objects.get(pk=work_id)
        except Work.DoesNotExist:
            return Response({'error': 'Work not found.'}, status=status.HTTP_404_NOT_FOUND)

        _check_work_access(request.user, work)

        try:
            parsed = parse_rm_pdf(file_obj)
        except Exception as e:
            return Response({'error': f'PDF parse failed: {e}'}, status=status.HTTP_400_BAD_REQUEST)

        if parsed.get('error'):
            return Response({'error': parsed['error']}, status=status.HTTP_400_BAD_REQUEST)

        warnings = []

        header        = parsed.get('header', {})
        agreement_pdf = (header.get('agreement') or '').strip()
        agreement_db  = (work.contract_agreement or '').strip()
        if agreement_pdf and agreement_db and agreement_pdf != agreement_db:
            warnings.append(
                f'Agreement reference mismatch: PDF says "{agreement_pdf}", '
                f'selected work has "{agreement_db}". Verify the right work is selected.'
            )

        all_items = list(WorkItem.objects.filter(work=work))

        def norm(s):
            s = str(s or '').strip()
            if s.endswith('.0'):
                s = s[:-2]
            return s.lstrip('0') or '0'

        index = {}
        for wi in all_items:
            sch = (wi.schedule or '').strip().upper()
            sch_letter = sch[0] if sch else ''
            key = (sch_letter, norm(wi.serial_number))
            index[key] = wi

        prior_qty_map = {}
        for row in (
            MBItem.objects
            .filter(work_item__work=work)
            .values('work_item_id')
            .annotate(t=Sum('quantity'))
        ):
            prior_qty_map[row['work_item_id']] = row['t'] or 0

        rows = []
        for src in parsed.get('items', []):
            sch_letter = (src.get('schedule') or '').upper()
            key = (sch_letter, src.get('item_no_norm') or norm(src.get('item_no')))
            wi  = index.get(key)
            cur_pct = src.get('current_percentage', 0)

            row = {
                'schedule':            sch_letter,
                'item_no':             src.get('item_no'),
                'description':         src.get('description'),
                'unit':                src.get('unit'),
                'quantity':            src.get('quantity', 0),
                'total_to_date':       src.get('total_to_date', 0),
                'current_percentage':  cur_pct,
                'not_received_warning': False,
            }

            if wi is None:
                row['matched']         = False
                row['work_item']       = None
                row['work_item_label'] = None
                warnings.append(
                    f'Item No. {src.get("item_no")} (Schedule {sch_letter}) not found in selected work.'
                )
            else:
                prior_qty = prior_qty_map.get(wi.id, 0)
                qty = src.get('quantity') or 0
                pdf_total = src.get('total_to_date') or 0
                # "Total" in the MB PDF is the per-record total, not cumulative.
                # Warn only if the Total line disagrees with the parsed measurement row.
                if pdf_total and qty and abs(pdf_total - qty) > 0.001:
                    warnings.append(
                        f'Item No. {src.get("item_no")}: parsed Total ({pdf_total}) does not match '
                        f'measurement row qty ({qty}). Check PDF or re-upload.'
                    )

                # Check received status before payment
                if cur_pct > 0:
                    is_sch_a = sch_letter == 'A'
                    if is_sch_a:
                        received_qty = wi.supplied_quantity or 0
                        if received_qty <= 0:
                            row['not_received_warning'] = True
                            warnings.append(
                                f'⚠ Item No. {src.get("item_no")} (Sch A): Payment of {cur_pct}% is being made '
                                f'but item has not been received (supplied quantity = 0). '
                                f'Please receive the item first.'
                            )
                    else:
                        executed_qty = wi.executed_quantity or 0
                        if executed_qty <= 0:
                            row['not_received_warning'] = True
                            warnings.append(
                                f'⚠ Item No. {src.get("item_no")} (Sch {sch_letter}): Payment of {cur_pct}% is being made '
                                f'but item has not been executed (executed quantity = 0). '
                                f'Please receive/execute the item first.'
                            )

                row['matched']         = True
                row['work_item']       = wi.id
                row['work_item_label'] = f'S.No {wi.serial_number} · {(wi.item_desc or "")[:80]}'
                row['unit_rate_below'] = wi.unit_rate_below or 0
                row['contract_qty']    = wi.qty or 0
                row['db_prior_qty']    = prior_qty

            rows.append(row)

        return Response({
            'header':   header,
            'items':    rows,
            'warnings': warnings,
        })
