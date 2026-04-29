from django.db.models import Sum
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, generics
from rest_framework.exceptions import PermissionDenied

from works.models import Work, WorkItem, WorkItemEntry, WorkExtension
from works.serializers import WorkItemEntrySerializer, WorkEditSerializer


def _check_not_observer(user):
    if user.is_authenticated and hasattr(user, 'profile') and user.profile.role == 'observer':
        raise PermissionDenied("Observers are not authorized to make changes.")


def _sync_item_quantities(work_item):
    """Recompute and save supplied_quantity and executed_quantity from current entries."""
    supply_total = (
        WorkItemEntry.objects
        .filter(work_item=work_item, entry_type='supply')
        .aggregate(t=Sum('quantity'))['t'] or 0
    )
    exec_total = (
        WorkItemEntry.objects
        .filter(work_item=work_item, entry_type='execution')
        .aggregate(t=Sum('quantity'))['t'] or 0
    )
    work_item.supplied_quantity = supply_total
    work_item.executed_quantity = exec_total
    work_item.save(update_fields=['supplied_quantity', 'executed_quantity'])


# ── Work-level edit / delete ──────────────────────────────────────────────────

class WorkUpdateDeleteView(generics.RetrieveUpdateDestroyAPIView):
    """PATCH /api/update-work/works/<pk>/  DELETE /api/update-work/works/<pk>/"""
    queryset = Work.objects.all()
    serializer_class = WorkEditSerializer

    def partial_update(self, request, *args, **kwargs):
        _check_not_observer(request.user)
        instance = self.get_object()

        serializer = WorkEditSerializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        if 'extensions' in request.data:
            instance.extensions.all().delete()
            for ext in request.data.get('extensions', []):
                date_val = (ext.get('extension_date') or '').strip()
                if date_val:
                    WorkExtension.objects.create(work=instance, extension_date=date_val)

        return Response(serializer.data)

    def perform_destroy(self, instance):
        _check_not_observer(self.request.user)
        instance.delete()


# ── Lot-entry submission ──────────────────────────────────────────────────────

class WorkItemEntryView(APIView):
    """
    GET  /api/update-work/items/<item_id>/entries/
    POST /api/update-work/items/<item_id>/entries/
    """

    def get(self, request, item_id):
        entries = WorkItemEntry.objects.filter(work_item_id=item_id).order_by('submitted_at')
        serializer = WorkItemEntrySerializer(entries, many=True)
        return Response(serializer.data)

    def post(self, request, item_id):
        _check_not_observer(request.user)

        try:
            work_item = WorkItem.objects.get(pk=item_id)
        except WorkItem.DoesNotExist:
            return Response({'error': 'Item not found.'}, status=status.HTTP_404_NOT_FOUND)

        # Validate quantity
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

        entry = WorkItemEntry.objects.create(
            work_item=work_item,
            entry_type=entry_type,
            quantity=qty,
            challan_no=request.data.get('challan_no', '') or '',
            udm_entry=request.data.get('udm_entry', '') or '',
            location=request.data.get('location', '') or '',
            remarks=request.data.get('remarks', '') or '',
            submitted_by=request.user if request.user.is_authenticated else None,
        )

        _sync_item_quantities(work_item)

        serializer = WorkItemEntrySerializer(entry)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


# ── Entry edit (owner only) ───────────────────────────────────────────────────

class WorkItemEntryUpdateView(APIView):
    """PATCH /api/update-work/entries/<entry_id>/  – edit own submitted entry."""

    def patch(self, request, entry_id):
        try:
            entry = WorkItemEntry.objects.select_related('work_item').get(pk=entry_id)
        except WorkItemEntry.DoesNotExist:
            return Response({'error': 'Entry not found.'}, status=status.HTTP_404_NOT_FOUND)

        if not request.user.is_authenticated or entry.submitted_by != request.user:
            raise PermissionDenied("You can only edit entries that you submitted.")

        # Update quantity
        if 'quantity' in request.data:
            try:
                qty = float(request.data['quantity'])
                if qty <= 0:
                    raise ValueError
                entry.quantity = qty
            except (ValueError, TypeError):
                return Response({'error': 'quantity must be a positive number.'}, status=status.HTTP_400_BAD_REQUEST)

        # Update type-specific fields
        for field in ('challan_no', 'udm_entry', 'location', 'remarks'):
            if field in request.data:
                setattr(entry, field, request.data[field] or '')

        entry.save()
        _sync_item_quantities(entry.work_item)

        serializer = WorkItemEntrySerializer(entry)
        return Response(serializer.data)
