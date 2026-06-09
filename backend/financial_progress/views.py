from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.db.models import Max

from works.models import Work
from .models import BillRecord, BillItem
from .serializers import BillRecordSerializer, BillItemSerializer
from .pdf_parser import parse_bill_pdf


def _is_authenticated(user):
    if not user.is_authenticated:
        return False
    return True


def _is_admin(user):
    if not user.is_authenticated:
        return False
    if user.is_staff:
        return True
    profile = getattr(user, 'profile', None)
    return profile is not None and profile.role == 'admin'


# ── Parse (preview only, no save) ────────────────────────────────────────────

class ParseBillPDFView(APIView):
    """
    POST /api/financial-progress/parse/
    Body: multipart — file (PDF), work_id (optional)
    Returns parsed bill data for user preview before saving.
    """

    def post(self, request):
        if not _is_authenticated(request.user):
            return Response({'error': 'Authentication required.'}, status=status.HTTP_401_UNAUTHORIZED)

        file_obj = request.FILES.get('file')
        if not file_obj:
            return Response({'error': 'No file provided.'}, status=status.HTTP_400_BAD_REQUEST)

        work_id = request.data.get('work_id')
        work    = None
        if work_id:
            try:
                work = Work.objects.get(pk=work_id)
            except Work.DoesNotExist:
                return Response({'error': 'Work not found.'}, status=status.HTTP_404_NOT_FOUND)

        parsed = parse_bill_pdf(file_obj)

        # LOA mismatch warning
        if work and parsed.get('loa_number'):
            pdf_loa  = str(parsed['loa_number']).strip().lstrip('0')
            work_loa = str(work.loa_number or '').strip().lstrip('0')
            if pdf_loa and work_loa and pdf_loa != work_loa:
                parsed['warnings'].append(
                    f'LOA mismatch: PDF has "{parsed["loa_number"]}" '
                    f'but this work has "{work.loa_number}".'
                )

        return Response(parsed)


# ── Bills list / create ───────────────────────────────────────────────────────

class BillListCreateView(APIView):
    """
    GET  /api/financial-progress/bills/?work_id=
    POST /api/financial-progress/bills/
    """

    def get(self, request):
        if not _is_authenticated(request.user):
            return Response({'error': 'Authentication required.'}, status=status.HTTP_401_UNAUTHORIZED)

        work_id = request.query_params.get('work_id')
        if not work_id:
            return Response({'error': 'work_id required.'}, status=status.HTTP_400_BAD_REQUEST)

        bills = BillRecord.objects.filter(work_id=work_id).prefetch_related('items')
        serializer = BillRecordSerializer(bills, many=True)
        return Response(serializer.data)

    def post(self, request):
        if not _is_authenticated(request.user):
            return Response({'error': 'Authentication required.'}, status=status.HTTP_401_UNAUTHORIZED)

        work_id = request.data.get('work_id')
        if not work_id:
            return Response({'error': 'work_id required.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            work = Work.objects.get(pk=work_id)
        except Work.DoesNotExist:
            return Response({'error': 'Work not found.'}, status=status.HTTP_404_NOT_FOUND)

        data = request.data

        # Prevent duplicate bill numbers for the same work
        bill_number = (data.get('bill_number') or '').strip()
        if bill_number and BillRecord.objects.filter(work=work, bill_number=bill_number).exists():
            return Response(
                {'error': f'Bill "{bill_number}" already saved for this work.'},
                status=status.HTTP_409_CONFLICT,
            )

        bill = BillRecord.objects.create(
            work             = work,
            bill_number      = bill_number,
            bill_date        = data.get('bill_date') or None,
            loa_number       = data.get('loa_number', ''),
            agreement_number = data.get('agreement_number', ''),
            uploaded_by      = request.user,
        )

        items_data = data.get('items', [])
        for item in items_data:
            # Skip items with zero contract value (nothing to track)
            rate = float(item.get('agreement_rate') or 0)
            qty  = float(item.get('current_agmt_qty') or 0)
            if rate == 0 or qty == 0:
                continue
            BillItem.objects.create(
                bill_record      = bill,
                schedule_name    = item.get('schedule_name', ''),
                item_number      = item.get('item_number', ''),
                description      = item.get('description', ''),
                unit             = item.get('unit', ''),
                agreement_rate   = rate,
                current_agmt_qty = qty,
                amt_total        = float(item.get('amt_total') or 0),
            )

        serializer = BillRecordSerializer(bill)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


# ── Bill delete ───────────────────────────────────────────────────────────────

class BillDeleteView(APIView):
    """DELETE /api/financial-progress/bills/<id>/  — admin only"""

    def delete(self, request, pk):
        if not _is_admin(request.user):
            return Response({'error': 'Admin only.'}, status=status.HTTP_403_FORBIDDEN)
        try:
            bill = BillRecord.objects.get(pk=pk)
        except BillRecord.DoesNotExist:
            return Response({'error': 'Bill not found.'}, status=status.HTTP_404_NOT_FOUND)
        bill.delete()
        return Response({'message': 'Bill deleted.'})


# ── Financial summary ─────────────────────────────────────────────────────────

class FinancialSummaryView(APIView):
    """
    GET /api/financial-progress/summary/?work_id=

    Returns per-item financial progress using the most recent bill data for each item.
    Items are grouped by schedule_name.
    """

    def get(self, request):
        if not _is_authenticated(request.user):
            return Response({'error': 'Authentication required.'}, status=status.HTTP_401_UNAUTHORIZED)

        work_id = request.query_params.get('work_id')
        if not work_id:
            return Response({'error': 'work_id required.'}, status=status.HTTP_400_BAD_REQUEST)

        # All items for this work, ordered by bill date desc so latest comes first
        all_items = (
            BillItem.objects
            .filter(bill_record__work_id=work_id)
            .select_related('bill_record')
            .order_by('schedule_name', 'item_number', '-bill_record__bill_date', '-bill_record__id')
        )

        # Keep only the latest bill's entry per (schedule, item_number)
        seen = set()
        latest_items = []
        for item in all_items:
            key = (item.schedule_name, item.item_number)
            if key not in seen:
                seen.add(key)
                latest_items.append(item)

        # Sort by schedule then item number (numeric sort for item_number)
        def sort_key(item):
            try:
                return (item.schedule_name, int(item.item_number))
            except (ValueError, TypeError):
                return (item.schedule_name, 0)

        latest_items.sort(key=sort_key)

        # Group by schedule
        schedules = {}
        for item in latest_items:
            sched = item.schedule_name
            if sched not in schedules:
                schedules[sched] = []
            cv = item.contract_value
            schedules[sched].append({
                'id':               item.id,
                'item_number':      item.item_number,
                'description':      item.description,
                'unit':             item.unit,
                'agreement_rate':   item.agreement_rate,
                'current_agmt_qty': item.current_agmt_qty,
                'contract_value':   cv,
                'amt_total':        item.amt_total,
                'progress_pct':     item.progress_pct,
                'bill_number':      item.bill_record.bill_number,
                'bill_date':        str(item.bill_record.bill_date or ''),
            })

        # Also compute schedule-level totals
        result = []
        for sched_name in sorted(schedules.keys()):
            items = schedules[sched_name]
            total_cv  = sum(i['contract_value'] for i in items)
            total_amt = sum(i['amt_total'] for i in items)
            result.append({
                'schedule_name':    sched_name,
                'contract_value':   round(total_cv, 2),
                'amt_total':        round(total_amt, 2),
                'progress_pct':     round(total_amt / total_cv * 100, 1) if total_cv else 0,
                'items':            items,
            })

        return Response(result)
