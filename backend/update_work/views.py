from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, generics
from rest_framework.exceptions import PermissionDenied

from django.db.models import Q

from works.models import Work, WorkExtension
from works.serializers import WorkEditSerializer, WorkSerializer
from works.utils import is_admin_user as _is_admin, is_assigned_consignee as _is_work_consignee
from work_details.views import _base_queryset


def _check_can_modify_work(user, work):
    """Admin (is_staff or role='admin') can modify any work's metadata.
    Assigned consignee can modify only their own LOA's metadata. Everyone else is forbidden."""
    if not user.is_authenticated:
        raise PermissionDenied("Authentication required.")
    if _is_admin(user):
        return
    if _is_work_consignee(user, work):
        return
    raise PermissionDenied("You are not authorised to update this work.")


# ── Work list — now scoped, since entry submission has moved to the new
# supply_details/execution_details apps and no longer needs this to stay open
# for every consignee. Admin sees everything; assigned consignee sees only
# their own LOA; unassigned consignee sees nothing (empty list / 404).

class UpdateWorkSearchView(generics.ListAPIView):
    serializer_class = WorkSerializer

    def get_queryset(self):
        queryset = _base_queryset()
        if not _is_admin(self.request.user):
            queryset = queryset.filter(hrms_id=self.request.user.username)
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


class UpdateWorkRetrieveView(generics.RetrieveAPIView):
    serializer_class = WorkSerializer

    def retrieve(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return Response({'error': 'Login required.'}, status=status.HTTP_401_UNAUTHORIZED)
        return super().retrieve(request, *args, **kwargs)

    def get_queryset(self):
        queryset = _base_queryset()
        if not _is_admin(self.request.user):
            queryset = queryset.filter(hrms_id=self.request.user.username)
        return queryset


# ── Work-level edit / delete ──────────────────────────────────────────────────

class WorkUpdateDeleteView(generics.RetrieveUpdateDestroyAPIView):
    """PATCH /api/update-work/works/<pk>/  DELETE /api/update-work/works/<pk>/"""
    queryset = Work.objects.all()
    serializer_class = WorkEditSerializer

    def partial_update(self, request, *args, **kwargs):
        instance = self.get_object()
        _check_can_modify_work(request.user, instance)

        serializer = WorkEditSerializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        if 'extensions' in request.data:
            instance.extensions.all().delete()
            for ext in request.data.get('extensions', []):
                date_val = (ext.get('extension_date') or '').strip()
                if date_val:
                    ld_type = (ext.get('ld_type') or 'without_ld').strip()
                    ld_amount = (ext.get('ld_amount') or '').strip()
                    WorkExtension.objects.create(
                        work=instance,
                        extension_date=date_val,
                        ld_type=ld_type,
                        ld_amount=ld_amount if ld_type == 'with_ld' else '',
                    )

        return Response(serializer.data)

    def destroy(self, _request, *args, **kwargs):
        from rest_framework.response import Response
        return Response(
            {'error': 'Use DELETE /api/delete-log/works/<pk>/ with a reason to delete an LOA.'},
            status=status.HTTP_403_FORBIDDEN,
        )


# ── Lot-entry submission ──────────────────────────────────────────────────────

class WorkItemEntryView(APIView):
    """
    GET  /api/update-work/items/<item_id>/entries/
    POST /api/update-work/items/<item_id>/entries/
    """

    def get(self, request, item_id):
        _check_authenticated(request.user)
        entries = (
            WorkItemEntry.objects
            .filter(work_item_id=item_id)
            .order_by(
                db_models.F('date_of_receipt').asc(nulls_last=True),
                'submitted_at',
            )
        )
        serializer = WorkItemEntrySerializer(entries, many=True)
        return Response(serializer.data)

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

        entry_type = request.data.get('entry_type', 'supply')
        if entry_type not in ('supply', 'execution'):
            entry_type = 'supply'

        # ── Category-based access control ──────────────────────────────────────
        work = work_item.work
        category = (work_item.category or '').strip()
        user_is_primary_consignee = _is_work_consignee(request.user, work)

        if category == 'supply':
            if entry_type == 'execution':
                return Response(
                    {'error': 'Supply items do not have execution entries.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if not user_is_primary_consignee:
                return Response(
                    {'error': 'Only the assigned consignee for this work can submit supply entries.'},
                    status=status.HTTP_403_FORBIDDEN,
                )
        elif category == 'supply_installation':
            if entry_type == 'supply' and not user_is_primary_consignee:
                return Response(
                    {'error': 'Only the assigned consignee for this work can submit the supply portion of Supply & Installation items.'},
                    status=status.HTTP_403_FORBIDDEN,
                )
        elif category == 'execution':
            if entry_type == 'supply':
                return Response(
                    {'error': 'Execution items do not have supply entries.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        # ── End category check ─────────────────────────────────────────────────

        receive_note_no = (request.data.get('receive_note_no') or '').strip()
        if entry_type == 'supply' and receive_note_no:
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
            entry_type=entry_type,
            quantity=qty,
            # Supply fields
            receive_note_no=receive_note_no,
            date_of_receipt=request.data.get('date_of_receipt') or None,
            challan_no=request.data.get('challan_no') or '',
            udm_entry=request.data.get('udm_entry') or '',
            # Execution fields
            location=request.data.get('location') or '',
            remarks=request.data.get('remarks') or '',
            submitted_by=request.user if request.user.is_authenticated else None,
            submitted_by_designation=getattr(getattr(request.user, 'profile', None), 'designation', None),
        )

        _sync_item_quantities(work_item)

        serializer = WorkItemEntrySerializer(entry)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


# ── Entry edit ────────────────────────────────────────────────────────────────

class WorkItemEntryUpdateView(APIView):
    """PATCH /api/update-work/entries/<entry_id>/  – only submitter or admin may edit."""

    def patch(self, request, entry_id):
        if not request.user.is_authenticated:
            raise PermissionDenied("Authentication required.")

        try:
            entry = WorkItemEntry.objects.select_related('work_item__work').get(pk=entry_id)
        except WorkItemEntry.DoesNotExist:
            return Response({'error': 'Entry not found.'}, status=status.HTTP_404_NOT_FOUND)

        if entry.submitted_by_id != request.user.id and not _is_admin(request.user):
            raise PermissionDenied("Only the consignee who submitted this entry can edit it.")

        # Supply entries also require the user to still be the primary consignee of the work.
        # If the work was reassigned, the previous consignee loses edit access to supply entries.
        if entry.entry_type == 'supply' and not _is_admin(request.user):
            work = entry.work_item.work
            if not _is_work_consignee(request.user, work):
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

        for field in ('challan_no', 'udm_entry', 'receive_note_no', 'location', 'remarks'):
            if field in request.data:
                setattr(entry, field, request.data[field] or '')

        if 'date_of_receipt' in request.data:
            entry.date_of_receipt = request.data['date_of_receipt'] or None

        entry.save()
        _sync_item_quantities(entry.work_item)

        serializer = WorkItemEntrySerializer(entry)
        return Response(serializer.data)


# ── PDF parsing ───────────────────────────────────────────────────────────────

class ParsePDFsView(APIView):
    """
    POST /api/update-work/parse-pdfs/
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
