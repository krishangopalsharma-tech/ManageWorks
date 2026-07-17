from django.db import models as db_models
from django.db.models import Q, Sum
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, generics
from rest_framework.exceptions import PermissionDenied

from works.models import Work, WorkItem, WorkItemEntry
from works.serializers import WorkItemEntrySerializer, WorkSerializer
from works.utils import is_admin_user
from work_details.views import _base_queryset


def _check_authenticated(user):
    if not user.is_authenticated:
        raise PermissionDenied("Authentication required.")


def _sync_executed_quantity(work_item):
    """Recompute and save executed_quantity from current execution entries."""
    exec_total = (
        WorkItemEntry.objects
        .filter(work_item=work_item, entry_type='execution')
        .aggregate(t=Sum('quantity'))['t'] or 0
    )
    work_item.executed_quantity = exec_total
    work_item.save(update_fields=['executed_quantity'])


# ── Work list — unscoped ───────────────────────────────────────────────────────
# Execution entries have no ownership restriction — any consignee (assigned
# anywhere or nowhere) can submit an execution entry on any LOA, so every
# consignee needs to be able to find any LOA here.

class ExecutionWorkSearchView(generics.ListAPIView):
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


class ExecutionWorkRetrieveView(generics.RetrieveAPIView):
    serializer_class = WorkSerializer
    queryset = _base_queryset()

    def retrieve(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return Response({'error': 'Login required.'}, status=status.HTTP_401_UNAUTHORIZED)
        return super().retrieve(request, *args, **kwargs)


# ── Execution entry submission ─────────────────────────────────────────────────

class ExecutionEntryView(APIView):
    """
    GET  /api/execution-details/items/<item_id>/entries/  — execution entries for this item
    POST /api/execution-details/items/<item_id>/entries/  — submit an execution entry
    """

    def get(self, request, item_id):
        _check_authenticated(request.user)
        entries = (
            WorkItemEntry.objects
            .filter(work_item_id=item_id, entry_type='execution')
            .order_by('submitted_at')
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

        category = (work_item.category or '').strip()
        if category == WorkItem.CATEGORY_SUPPLY:
            return Response(
                {'error': 'Supply items do not have execution entries.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Execution Details is view-only for Admin/Super Admin. Any consignee
        # (assigned here, assigned elsewhere, or fully unassigned) may submit —
        # execution entries have no ownership restriction among consignees.
        if is_admin_user(request.user):
            return Response(
                {'error': 'Admins cannot submit execution entries — view only.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        entry = WorkItemEntry.objects.create(
            work_item=work_item,
            entry_type='execution',
            quantity=qty,
            location=request.data.get('location') or '',
            remarks=request.data.get('remarks') or '',
            submitted_by=request.user,
            submitted_by_designation=getattr(getattr(request.user, 'profile', None), 'designation', None),
        )

        _sync_executed_quantity(work_item)

        return Response(WorkItemEntrySerializer(entry).data, status=status.HTTP_201_CREATED)


class ExecutionEntryUpdateView(APIView):
    """PATCH /api/execution-details/entries/<entry_id>/ — only the submitter may edit.
    Admin/Super Admin is view-only on Execution Details — no create, no edit."""

    def patch(self, request, entry_id):
        if not request.user.is_authenticated:
            raise PermissionDenied("Authentication required.")

        try:
            entry = WorkItemEntry.objects.select_related('work_item__work').get(pk=entry_id, entry_type='execution')
        except WorkItemEntry.DoesNotExist:
            return Response({'error': 'Entry not found.'}, status=status.HTTP_404_NOT_FOUND)

        if entry.submitted_by_id != request.user.id:
            raise PermissionDenied("Only the consignee who submitted this entry can edit it.")

        if 'quantity' in request.data:
            try:
                qty = float(request.data['quantity'])
                if qty <= 0:
                    raise ValueError
                entry.quantity = qty
            except (ValueError, TypeError):
                return Response({'error': 'quantity must be a positive number.'}, status=status.HTTP_400_BAD_REQUEST)

        for field in ('location', 'remarks'):
            if field in request.data:
                setattr(entry, field, request.data[field] or '')

        entry.save()
        _sync_executed_quantity(entry.work_item)

        return Response(WorkItemEntrySerializer(entry).data)
