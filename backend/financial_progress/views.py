from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.db.models import Max, Count
from django.contrib.auth.models import User

from works.models import Work, WorkItem
from works.utils import contractor_nickname as _nickname, is_admin_user as _is_admin, is_assigned_consignee
from users.views import _is_super_admin
from .models import BillRecord, BillItem
from .serializers import BillRecordSerializer, BillItemSerializer
from .pdf_parser import parse_bill_pdf


def _normalize_serial(sno):
    """Normalize serial number for matching: strip leading zeros so '01' == '1'."""
    try:
        return str(int(sno))
    except (ValueError, TypeError):
        return (sno or '').strip()


def _build_loa_lookup(work):
    """Return {(schedule_upper, normalized_serial): WorkItem} for all items of a work."""
    lookup = {}
    for wi in WorkItem.objects.filter(work=work):  # type: ignore[attr-defined]
        sch = (wi.schedule or '').strip().upper()
        sno = _normalize_serial(wi.serial_number)
        if sch and sno:
            lookup[(sch, sno)] = wi
    return lookup


def _loa_cross_check(parsed, loa_lookup):
    """
    Augment each parsed item with loa_contract_value from WorkItem.
    Adds per-item warnings for overpayment and items missing from LOA.
    Replaces grand-total warning with LOA-based comparison.
    """
    if not loa_lookup:
        return

    missing_from_loa = []
    over_limit = []
    loa_matched_total = 0.0

    for item in parsed['items']:
        sch = item['schedule_name'].upper()
        sno = _normalize_serial(item['item_number'])
        wi  = loa_lookup.get((sch, sno))

        if wi is None:
            item['loa_contract_value'] = None
            missing_from_loa.append(f'Sch {sch} Item {sno}')
        else:
            loa_cv = wi.total_amount or 0.0
            item['loa_contract_value'] = loa_cv
            # unit_rate_below IS the per-unit agreement rate (in rupees, not a percentage)
            # Do NOT touch agreement_rate — PDF col 4 already has the correct contracted rate
            loa_matched_total += loa_cv
            if loa_cv > 0 and item['amt_total'] > loa_cv * 1.01:
                over_limit.append(
                    f'Sch {sch} Item {sno}: paid ₹{item["amt_total"]:,.0f} '
                    f'but LOA contract value is ₹{loa_cv:,.0f}'
                )

    if missing_from_loa:
        parsed['warnings'].append(
            'Items not found in LOA (may be variation/new items): '
            + ', '.join(missing_from_loa)
        )
    for msg in over_limit:
        parsed['warnings'].append(f'Overpayment warning — {msg}')

    # Store LOA matched total for reference (not compared against bill payment — they're different concepts)
    parsed['loa_grand_total'] = round(loa_matched_total, 2)


def _is_authenticated(user):
    if not user.is_authenticated:
        return False
    return True


def _can_access_work(user, work):
    """Admin sees all LOAs. Assigned consignee sees only their LOA. Unassigned sees nothing."""
    if _is_admin(user):
        return True
    return (work.hrms_id or '') == user.username


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
            if not _can_access_work(request.user, work):
                return Response({'error': 'Access denied.'}, status=status.HTTP_403_FORBIDDEN)

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

        # LOA cross-check: augment items with contract values, flag overpayments
        if work:
            loa_lookup = _build_loa_lookup(work)
            _loa_cross_check(parsed, loa_lookup)

        return Response(parsed)


# ── LOA item lookup (for auto-fill when adding missing items) ─────────────────

class LOAItemLookupView(APIView):
    """
    GET /api/financial-progress/loa-item/
        ?work_id=5&schedule=A2&item=15

    Returns WorkItem fields so the frontend can auto-fill the "Add missing item" form.
    """

    def get(self, request):
        if not _is_authenticated(request.user):
            return Response({'error': 'Authentication required.'}, status=status.HTTP_401_UNAUTHORIZED)

        work_id  = request.query_params.get('work_id')
        schedule = (request.query_params.get('schedule') or '').strip().upper()
        item_no  = (request.query_params.get('item') or '').strip()

        if not work_id or not schedule or not item_no:
            return Response({'error': 'work_id, schedule, and item are required.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            work = Work.objects.get(pk=work_id)
        except Work.DoesNotExist:
            return Response({'error': 'Work not found.'}, status=status.HTTP_404_NOT_FOUND)
        if not _can_access_work(request.user, work):
            return Response({'error': 'Access denied.'}, status=status.HTTP_403_FORBIDDEN)

        wi = WorkItem.objects.filter(  # type: ignore[attr-defined]
            work=work,
            schedule__iexact=schedule,
            serial_number=item_no,
        ).first()

        if wi is None:
            return Response({'found': False})

        below = wi.unit_rate_below or 0.0
        rate  = round(wi.unit_rate_rs * (1 - below / 100), 4) if wi.unit_rate_rs else 0.0

        return Response({
            'found':              True,
            'description':        wi.item_desc or '',
            'unit':               wi.unit or '',
            'agreement_rate':     rate,
            'current_agmt_qty':   wi.qty or 0,
            'loa_contract_value': wi.total_amount or 0,
        })


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

        try:
            work = Work.objects.get(pk=work_id)
        except Work.DoesNotExist:
            return Response({'error': 'Work not found.'}, status=status.HTTP_404_NOT_FOUND)
        if not _can_access_work(request.user, work):
            return Response({'error': 'Access denied.'}, status=status.HTTP_403_FORBIDDEN)

        bills = BillRecord.objects.filter(work=work).prefetch_related('items')
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
        if not _can_access_work(request.user, work):
            return Response({'error': 'Access denied.'}, status=status.HTTP_403_FORBIDDEN)

        data = request.data

        # Reject if LOA number in submitted data doesn't match work's LOA
        submitted_loa = str(data.get('loa_number') or '').strip().lstrip('0')
        work_loa      = str(work.loa_number or '').strip().lstrip('0')
        if submitted_loa and work_loa and submitted_loa != work_loa:
            return Response(
                {'error': f'LOA mismatch: bill belongs to "{data.get("loa_number")}" but this work is "{work.loa_number}". Cannot save.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Prevent duplicate bill numbers for the same work
        bill_number = (data.get('bill_number') or '').strip()
        if bill_number and BillRecord.objects.filter(work=work, bill_number=bill_number).exists():
            return Response(
                {'error': f'Bill "{bill_number}" already saved for this work.'},
                status=status.HTTP_409_CONFLICT,
            )

        raw_override = data.get('total_amount_override')
        override_val = float(raw_override) if raw_override not in (None, '', '0', 0) else None

        bill = BillRecord.objects.create(
            work                  = work,
            bill_number           = bill_number,
            bill_date             = data.get('bill_date') or None,
            loa_number            = data.get('loa_number', ''),
            agreement_number      = data.get('agreement_number', ''),
            uploaded_by           = request.user,
            total_amount_override = override_val,
        )

        items_data = data.get('items', [])
        for item in items_data:
            rate = float(item.get('agreement_rate') or 0)
            qty  = float(item.get('current_agmt_qty') or 0)
            amt  = float(item.get('amt_total') or 0)
            # Skip items with no contract data and no payment
            if rate == 0 and qty == 0 and amt == 0:
                continue
            BillItem.objects.create(
                bill_record      = bill,
                schedule_name    = item.get('schedule_name', ''),
                item_number      = item.get('item_number', ''),
                description      = item.get('description', ''),
                unit             = item.get('unit', ''),
                agreement_rate   = rate,
                current_agmt_qty = qty,
                qty_upto_date    = float(item.get('qty_upto_date') or 0),
                amt_total        = float(item.get('amt_total') or 0),
            )

        serializer = BillRecordSerializer(bill)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


# ── Bill delete ───────────────────────────────────────────────────────────────

def _can_delete_or_edit_bill(user, work):
    """Super Admin can delete/edit any bill. Assigned consignee can delete/edit their own LOA's bill.
    Plain Admin (view-only per spec) and unassigned consignees get no delete/edit rights."""
    return _is_super_admin(user) or is_assigned_consignee(user, work)


class BillDeleteView(APIView):
    """
    GET    /api/financial-progress/bills/<id>/  — returns bill + items
    DELETE /api/financial-progress/bills/<id>/  — super admin (any LOA) or assigned consignee (own LOA)
    PATCH  /api/financial-progress/bills/<id>/  — same as DELETE; accepts items[] to replace all items
    """

    def get(self, request, pk):
        if not _is_authenticated(request.user):
            return Response({'error': 'Authentication required.'}, status=status.HTTP_401_UNAUTHORIZED)
        try:
            bill = BillRecord.objects.select_related('work').prefetch_related('items').get(pk=pk)
        except BillRecord.DoesNotExist:
            return Response({'error': 'Bill not found.'}, status=status.HTTP_404_NOT_FOUND)
        if not _can_access_work(request.user, bill.work):
            return Response({'error': 'Access denied.'}, status=status.HTTP_403_FORBIDDEN)
        return Response(BillRecordSerializer(bill).data)

    def delete(self, request, pk):
        try:
            bill = BillRecord.objects.select_related('work').get(pk=pk)
        except BillRecord.DoesNotExist:
            return Response({'error': 'Bill not found.'}, status=status.HTTP_404_NOT_FOUND)
        if not _can_delete_or_edit_bill(request.user, bill.work):
            return Response({'error': 'Forbidden.'}, status=status.HTTP_403_FORBIDDEN)
        bill.delete()
        return Response({'message': 'Bill deleted.'})

    def patch(self, request, pk):
        try:
            bill = BillRecord.objects.select_related('work').get(pk=pk)
        except BillRecord.DoesNotExist:
            return Response({'error': 'Bill not found.'}, status=status.HTTP_404_NOT_FOUND)
        if not _can_delete_or_edit_bill(request.user, bill.work):
            return Response({'error': 'Forbidden.'}, status=status.HTTP_403_FORBIDDEN)
        if 'bill_number' in request.data:
            bill.bill_number = str(request.data['bill_number']).strip()
        if 'bill_date' in request.data:
            bill.bill_date = request.data['bill_date'] or None
        if 'total_amount_override' in request.data:
            v = request.data['total_amount_override']
            bill.total_amount_override = float(v) if v not in (None, '', '0', 0) else None
        bill.save()
        if 'items' in request.data:
            bill.items.all().delete()
            for item in request.data['items']:
                rate = float(item.get('agreement_rate') or 0)
                qty  = float(item.get('current_agmt_qty') or 0)
                amt  = float(item.get('amt_total') or 0)
                if rate == 0 and qty == 0 and amt == 0:
                    continue
                BillItem.objects.create(
                    bill_record      = bill,
                    schedule_name    = item.get('schedule_name', ''),
                    item_number      = item.get('item_number', ''),
                    description      = item.get('description', ''),
                    unit             = item.get('unit', ''),
                    agreement_rate   = rate,
                    current_agmt_qty = qty,
                    qty_upto_date    = float(item.get('qty_upto_date') or 0),
                    amt_total        = amt,
                )
        return Response(BillRecordSerializer(bill).data)


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

        try:
            work = Work.objects.get(pk=work_id)
        except Work.DoesNotExist:
            return Response({'error': 'Work not found.'}, status=status.HTTP_404_NOT_FOUND)
        if not _can_access_work(request.user, work):
            return Response({'error': 'Access denied.'}, status=status.HTTP_403_FORBIDDEN)

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


# ── Works list ───────────────────────────────────────────────────────────────

class WorkListView(APIView):
    """GET /api/financial-progress/works/"""

    def get(self, request):
        if not _is_authenticated(request.user):
            return Response({'error': 'Authentication required.'}, status=status.HTTP_401_UNAUTHORIZED)

        qs = Work.objects.annotate(
            bill_count=Count('bill_records', distinct=True),
        ).order_by('loa_number')

        if not _is_admin(request.user):
            qs = qs.filter(hrms_id=request.user.username)

        # Build username→display map for consignees in one query
        usernames = [w.hrms_id for w in qs if w.hrms_id]
        user_map = {}
        for u in User.objects.filter(username__in=usernames).select_related('profile'):
            name = u.first_name or u.username
            try:
                desig = u.profile.designation
            except Exception:
                desig = None
            user_map[u.username] = f"{name} ({desig})" if desig else name

        data = []
        for w in qs:
            consignee_display = user_map.get(w.hrms_id or '') or w.consignee or ''
            data.append({
                'id':                  w.id,
                'loa_number':          w.loa_number or '',
                'tender_number':       w.tender_number or '',
                'name_of_work':        w.name_of_work or '',
                'contractor_name':     w.contractor_name or '',
                'contractor_nickname': _nickname(w.contractor_name or ''),
                'consignee':           w.consignee or '',
                'consignee_display':   consignee_display,
                'date_of_completion':  w.date_of_completion or '',
                'bill_count':          w.bill_count,
            })
        return Response(data)


# ── LOA table (per-bill breakdown for financial progress table) ───────────────

class LOATableView(APIView):
    """
    GET /api/financial-progress/loa-table/?work_id=

    Returns:
      bills  – ordered list of BillRecord stubs
      items  – items with financial progress, each carrying per-bill amounts
    """

    def get(self, request):
        if not _is_authenticated(request.user):
            return Response({'error': 'Authentication required.'}, status=status.HTTP_401_UNAUTHORIZED)

        work_id = request.query_params.get('work_id')
        if not work_id:
            return Response({'error': 'work_id required.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            work = Work.objects.get(pk=work_id)
        except Work.DoesNotExist:
            return Response({'error': 'Work not found.'}, status=status.HTTP_404_NOT_FOUND)
        if not _can_access_work(request.user, work):
            return Response({'error': 'Access denied.'}, status=status.HTTP_403_FORBIDDEN)

        bills = list(
            BillRecord.objects
            .filter(work_id=work_id)
            .order_by('bill_date', 'id')
            .values('id', 'bill_number', 'bill_date', 'total_amount_override')
        )

        # All BillItems for this work, newest bill first (for cumulative = latest)
        all_bill_items = (
            BillItem.objects
            .filter(bill_record__work_id=work_id)
            .select_related('bill_record')
            .order_by('schedule_name', 'item_number', 'bill_record__bill_date', 'bill_record__id')
        )

        # Collect per-item data keyed by (schedule_name, item_number)
        item_map = {}   # (sch, item_no) → dict with bill_data
        for bi in all_bill_items:
            key = (bi.schedule_name, bi.item_number)
            if key not in item_map:
                item_map[key] = {
                    'schedule_name':    bi.schedule_name,
                    'item_number':      bi.item_number,
                    'description':      bi.description,
                    'unit':             bi.unit,
                    'bill_data':        {},
                    'cumulative_amount': 0,
                    'progress_pct':      0,
                    'agreement_rate':    0,
                    'current_agmt_qty':  0,
                    'contract_value':    0,
                }
            entry = item_map[key]
            entry['bill_data'][str(bi.bill_record_id)] = {
                'amount':         bi.amt_total,   # period amount for this bill
                'qty':            bi.current_agmt_qty,
                'qty_upto_date':  bi.qty_upto_date,
                'pct':            bi.progress_pct,
            }
            # Accumulate period amounts → gives true cumulative
            entry['cumulative_amount'] += bi.amt_total
            # Overwrite with latest bill's metadata
            entry['agreement_rate']   = bi.agreement_rate
            entry['current_agmt_qty'] = bi.current_agmt_qty
            entry['contract_value']   = bi.contract_value

        # Compute cumulative progress_pct from summed period amounts
        for entry in item_map.values():
            cv = entry['contract_value']
            entry['progress_pct'] = round(min(entry['cumulative_amount'] / cv * 100, 100), 1) if cv else 0.0

        def sort_key(item):
            try:
                return (item['schedule_name'], int(item['item_number']))
            except (ValueError, TypeError):
                return (item['schedule_name'], 0)

        items = sorted(item_map.values(), key=sort_key)

        total_paid     = round(sum(i['cumulative_amount'] for i in items), 2)
        total_contract = round(sum(i['contract_value']    for i in items), 2)

        # Apply manual overrides: replace a bill's parsed contribution with override amount
        override_map = {b['id']: b['total_amount_override'] for b in bills if b.get('total_amount_override') is not None}
        if override_map:
            bill_parsed = {}
            for i in items:
                for bid_str, bd in i['bill_data'].items():
                    bid = int(bid_str)
                    bill_parsed[bid] = bill_parsed.get(bid, 0) + (bd['amount'] or 0)
            for bid, override_amt in override_map.items():
                total_paid += override_amt - bill_parsed.get(bid, 0)
            total_paid = round(total_paid, 2)

        overall_pct = round(total_paid / total_contract * 100, 2) if total_contract else 0

        return Response({
            'bills':  bills,
            'items':  items,
            'totals': {
                'total_paid':     total_paid,
                'total_contract': total_contract,
                'overall_pct':    overall_pct,
            },
        })
