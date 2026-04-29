from django.db import transaction
from django.db.models import Sum, Max, Q
from rest_framework import status, generics
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied

from works.models import Work, WorkItem
from .models import MBRecord, MBItem
from .serializers import MBRecordSerializer


def _check_not_observer(user):
    if user.is_authenticated and hasattr(user, 'profile') and user.profile.role == 'observer':
        raise PermissionDenied("Observers are not authorized to make changes.")


class WorkSearchView(APIView):
    """GET /api/mb-details/works/?q=loa"""

    def get(self, request):
        q = request.query_params.get('q', '').strip()
        qs = Work.objects.all()
        if q:
            qs = qs.filter(
                Q(loa_number__icontains=q) |
                Q(tender_number__icontains=q) |
                Q(contractor_name__icontains=q) |
                Q(consignee__icontains=q)
            )
        data = [
            {
                'id': w.id,
                'loa_number': w.loa_number or '',
                'tender_number': w.tender_number or '',
                'contractor_name': w.contractor_name or '',
                'consignee': w.consignee or '',
            }
            for w in qs[:50]
        ]
        return Response(data)


class WorkItemSearchView(APIView):
    """GET /api/mb-details/works/<work_id>/items/?schedule=A|B|&q=cable"""

    def get(self, request, work_id):
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


class ItemPriorInfoView(APIView):
    """
    GET /api/mb-details/items/<work_item_id>/prior/
    Returns suggested prior cumulative % (max current_percentage from prior MBs for this item)
    and other useful defaults.
    """

    def get(self, request, work_item_id):
        try:
            wi = WorkItem.objects.get(pk=work_item_id)
        except WorkItem.DoesNotExist:
            return Response({'error': 'Item not found.'}, status=status.HTTP_404_NOT_FOUND)

        prior_pct = MBItem.objects.filter(work_item=wi).aggregate(m=Max('current_percentage'))['m'] or 0
        billed_qty_total = MBItem.objects.filter(work_item=wi).aggregate(t=Sum('quantity'))['t'] or 0

        return Response({
            'suggested_prior_pct': prior_pct,
            'default_quantity':    wi.qty or 0,
            'unit_rate_below':     wi.unit_rate_below or 0,
            'billed_qty_total':    billed_qty_total,
        })


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
        work_id = self.request.query_params.get('work_id')
        if work_id:
            qs = qs.filter(work_id=work_id)
        return qs.order_by('-created_at')

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        _check_not_observer(request.user)

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

        if MBRecord.objects.filter(work=work, mb_number=mb_number).exists():
            return Response({'error': f'MB number "{mb_number}" already exists for this work.'},
                            status=status.HTTP_400_BAD_REQUEST)

        record = MBRecord.objects.create(
            work=work,
            mb_number=mb_number,
            notes=notes,
            created_by=request.user if request.user.is_authenticated else None,
        )

        for row in items:
            wi_id    = row.get('work_item')
            try:
                qty       = float(row.get('quantity') or 0)
                prior_pct = float(row.get('prior_percentage') or 0)
                cur_pct   = float(row.get('current_percentage') or 0)
            except (ValueError, TypeError):
                record.delete()
                return Response({'error': f'Invalid numeric values for item {wi_id}.'},
                                status=status.HTTP_400_BAD_REQUEST)

            if qty <= 0:
                continue
            if cur_pct <= prior_pct:
                record.delete()
                return Response({'error': f'current_percentage must exceed prior_percentage for item {wi_id}.'},
                                status=status.HTTP_400_BAD_REQUEST)
            if cur_pct > 100 or prior_pct < 0:
                record.delete()
                return Response({'error': f'percentages out of range for item {wi_id}.'},
                                status=status.HTTP_400_BAD_REQUEST)

            try:
                wi = WorkItem.objects.get(pk=wi_id, work=work)
            except WorkItem.DoesNotExist:
                record.delete()
                return Response({'error': f'Item {wi_id} not found in this work.'},
                                status=status.HTTP_404_NOT_FOUND)

            MBItem.objects.create(
                mb_record=record, work_item=wi,
                quantity=qty, prior_percentage=prior_pct, current_percentage=cur_pct, amount=0,
            )

        return Response(MBRecordSerializer(record).data, status=status.HTTP_201_CREATED)


class MBRecordDetailView(generics.RetrieveDestroyAPIView):
    """GET / DELETE /api/mb-details/records/<pk>/"""
    queryset         = MBRecord.objects.all()
    serializer_class = MBRecordSerializer

    def perform_destroy(self, instance):
        _check_not_observer(self.request.user)
        instance.delete()


class MBSummaryView(APIView):
    """
    GET /api/mb-details/summary/?work_id=
    Financial progress by schedule (via item.schedule, since MB is schedule-agnostic).
    """

    def get(self, request):
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
