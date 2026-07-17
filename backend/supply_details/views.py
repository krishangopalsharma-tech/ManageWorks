from django.db import models as db_models
from django.db.models import Q, Sum
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, generics
from rest_framework.exceptions import PermissionDenied

from works.models import Work, WorkItem, WorkItemEntry
from works.serializers import WorkItemEntrySerializer, WorkSerializer
from works.utils import is_admin_user, is_assigned_consignee
from work_details.views import _base_queryset
from .pdf_parser import parse_receipt_pdf


def _pad_loa(raw):
    """Normalise LOA to 14 digits — mirrors excel_parser logic."""
    s = str(raw or '').strip()
    if not s:
        return s
    if '.' in s:
        try:
            s = str(int(float(s)))
        except (ValueError, TypeError):
            pass
    if s.isdigit() and len(s) < 14:
        s = s.zfill(14)
    return s


def _check_authenticated(user):
    if not user.is_authenticated:
        raise PermissionDenied("Authentication required.")


def _sync_supplied_quantity(work_item):
    """Recompute and save supplied_quantity from current supply entries."""
    supply_total = (
        WorkItemEntry.objects
        .filter(work_item=work_item, entry_type='supply')
        .aggregate(t=Sum('quantity'))['t'] or 0
    )
    work_item.supplied_quantity = supply_total
    work_item.save(update_fields=['supplied_quantity'])


# ── Work list — unscoped ───────────────────────────────────────────────────────
# Every consignee (assigned or not) needs to find any LOA to view its Supply
# Details (SS + supply-portion of SI items); actual entry submission is gated
# per-item below (assigned consignee only, per category).

class SupplyWorkSearchView(generics.ListAPIView):
    serializer_class = WorkSerializer

    def get_queryset(self):
        queryset = _base_queryset()
        query = self.request.query_params.get('q', None)
        if query:
            queryset = queryset.filter(
                Q(loa_number__icontains=query) |
                Q(contractor_name__icontains=query) |
                Q(tender_number__icontains=query)
            )
        return queryset

    def list(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return Response({'error': 'Login required.'}, status=status.HTTP_401_UNAUTHORIZED)
        return super().list(request, *args, **kwargs)


class SupplyWorkRetrieveView(generics.RetrieveAPIView):
    serializer_class = WorkSerializer
    queryset = _base_queryset()

    def retrieve(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return Response({'error': 'Login required.'}, status=status.HTTP_401_UNAUTHORIZED)
        return super().retrieve(request, *args, **kwargs)


# ── Supply entry submission ────────────────────────────────────────────────────

class SupplyEntryView(APIView):
    """
    GET  /api/supply-details/items/<item_id>/entries/  — supply entries for this item
    POST /api/supply-details/items/<item_id>/entries/  — submit a supply entry
    """

    def get(self, request, item_id):
        _check_authenticated(request.user)
        entries = (
            WorkItemEntry.objects
            .filter(work_item_id=item_id, entry_type='supply')
            .order_by(
                db_models.F('date_of_receipt').asc(nulls_last=True),
                'submitted_at',
            )
        )
        return Response(WorkItemEntrySerializer(entries, many=True).data)

    def post(self, request, item_id):
        _check_authenticated(request.user)

        try:
            work_item = WorkItem.objects.select_related('work').get(pk=item_id)
        except WorkItem.DoesNotExist:
            return Response({'error': 'Item not found.'}, status=status.HTTP_404_NOT_FOUND)

        qty = request.data.get('quantity')
        if qty is None or qty == '':
            return Response({'error': 'quantity is required.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            qty = float(qty)
            if qty <= 0:
                raise ValueError
        except (ValueError, TypeError):
            return Response({'error': 'quantity must be a positive number.'}, status=status.HTTP_400_BAD_REQUEST)

        work = work_item.work
        category = (work_item.category or '').strip()

        if category == WorkItem.CATEGORY_EXECUTION:
            return Response(
                {'error': 'Execution items do not have supply entries.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # SS and the supply-portion of SI items are restricted to the assigned consignee.
        if not is_admin_user(request.user) and not is_assigned_consignee(request.user, work):
            return Response(
                {'error': 'Only the assigned consignee for this work can submit supply entries.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        receive_note_no = (request.data.get('receive_note_no') or '').strip()
        if receive_note_no:
            if WorkItemEntry.objects.filter(
                entry_type='supply',
                receive_note_no=receive_note_no,
            ).exists():
                return Response(
                    {'error': f'Receive Note No. "{receive_note_no}" already exists. Consignee cannot accept the same receipt twice.'},
                    status=status.HTTP_409_CONFLICT,
                )

        entry = WorkItemEntry.objects.create(
            work_item=work_item,
            entry_type='supply',
            quantity=qty,
            receive_note_no=receive_note_no,
            date_of_receipt=request.data.get('date_of_receipt') or None,
            challan_no=request.data.get('challan_no') or '',
            udm_entry=request.data.get('udm_entry') or '',
            submitted_by=request.user,
            submitted_by_designation=getattr(getattr(request.user, 'profile', None), 'designation', None),
        )

        _sync_supplied_quantity(work_item)

        return Response(WorkItemEntrySerializer(entry).data, status=status.HTTP_201_CREATED)


class SupplyEntryUpdateView(APIView):
    """PATCH /api/supply-details/entries/<entry_id>/ — only submitter or admin may edit."""

    def patch(self, request, entry_id):
        if not request.user.is_authenticated:
            raise PermissionDenied("Authentication required.")

        try:
            entry = WorkItemEntry.objects.select_related('work_item__work').get(pk=entry_id, entry_type='supply')
        except WorkItemEntry.DoesNotExist:
            return Response({'error': 'Entry not found.'}, status=status.HTTP_404_NOT_FOUND)

        if entry.submitted_by_id != request.user.id and not is_admin_user(request.user):
            raise PermissionDenied("Only the consignee who submitted this entry can edit it.")

        # Supply entries also require the user to still be the primary consignee of the
        # work. If the work was reassigned, the previous consignee loses edit access.
        if not is_admin_user(request.user):
            work = entry.work_item.work
            if not is_assigned_consignee(request.user, work):
                raise PermissionDenied(
                    "This work has been reassigned. You no longer have permission to edit supply entries."
                )

        if 'quantity' in request.data:
            try:
                qty = float(request.data['quantity'])
                if qty <= 0:
                    raise ValueError
                entry.quantity = qty
            except (ValueError, TypeError):
                return Response({'error': 'quantity must be a positive number.'}, status=status.HTTP_400_BAD_REQUEST)

        for field in ('challan_no', 'udm_entry', 'receive_note_no'):
            if field in request.data:
                setattr(entry, field, request.data[field] or '')

        if 'date_of_receipt' in request.data:
            entry.date_of_receipt = request.data['date_of_receipt'] or None

        entry.save()
        _sync_supplied_quantity(entry.work_item)

        return Response(WorkItemEntrySerializer(entry).data)


# ── PDF parsing ─────────────────────────────────────────────────────────────────

class ParseSupplyPDFsView(APIView):
    """
    POST /api/supply-details/parse-pdfs/
    Accepts one or more PDF files (field name: 'files').
    Returns a list of parsed receipt data for user review before submission.
    """

    def post(self, request):
        _check_authenticated(request.user)

        files = request.FILES.getlist('files')
        if not files:
            return Response({'error': 'No files provided.'}, status=status.HTTP_400_BAD_REQUEST)

        work = None
        work_id = request.data.get('work_id')
        if work_id:
            try:
                work = Work.objects.get(pk=work_id)
            except Work.DoesNotExist:
                return Response({'error': 'Work not found.'}, status=status.HTTP_404_NOT_FOUND)

        results = []
        for f in files:
            try:
                parsed = parse_receipt_pdf(f)
                parsed['filename'] = f.name
            except Exception as exc:
                parsed = {
                    'filename': f.name,
                    'parse_warnings': [f'Failed to parse: {exc}'],
                    'error': True,
                }
                results.append(parsed)
                continue

            if work and not parsed.get('error'):
                mismatch = []
                pdf_loa = _pad_loa(parsed.get('loa_number') or '').lower()
                work_loa = _pad_loa(work.loa_number or '').lower()
                if pdf_loa and work_loa and pdf_loa != work_loa:
                    mismatch.append(
                        f'LOA No. mismatch: PDF has "{parsed["loa_number"]}" '
                        f'but this work has "{work.loa_number}".'
                    )

                pdf_ca = (parsed.get('contract_agreement') or '').strip().lower()
                work_ca = (work.contract_agreement or '').strip().lower()
                if pdf_ca and work_ca and pdf_ca != work_ca:
                    mismatch.append(
                        f'Contract Agreement No. mismatch: PDF has "{parsed["contract_agreement"]}" '
                        f'but this work has "{work.contract_agreement}".'
                    )

                if mismatch:
                    parsed['error'] = True
                    parsed['parse_warnings'] = (parsed.get('parse_warnings') or []) + mismatch

            results.append(parsed)

        return Response(results)
