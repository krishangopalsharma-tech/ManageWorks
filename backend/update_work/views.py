from django.db.models import Sum
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, generics
from rest_framework.exceptions import PermissionDenied

from works.models import Work, WorkItem, WorkItemEntry, WorkExtension, WorkBill
from works.serializers import WorkItemEntrySerializer, WorkEditSerializer


def _check_not_observer(user):
    """Raise PermissionDenied if the authenticated user is an Observer."""
    if user.is_authenticated and hasattr(user, 'profile') and user.profile.role == 'observer':
        raise PermissionDenied("Observers are not authorized to make changes.")


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

        # Replace extensions if provided in payload
        if 'extensions' in request.data:
            instance.extensions.all().delete()
            for ext in request.data.get('extensions', []):
                date_val = (ext.get('extension_date') or '').strip()
                if date_val:
                    WorkExtension.objects.create(work=instance, extension_date=date_val)

        # Replace bills if provided in payload
        if 'bills' in request.data:
            instance.bills.all().delete()
            for bill in request.data.get('bills', []):
                try:
                    amt = float(bill.get('bill_amount') or 0)
                    if amt > 0:
                        WorkBill.objects.create(work=instance, bill_amount=amt)
                except (ValueError, TypeError):
                    pass

        return Response(serializer.data)

    def perform_destroy(self, instance):
        _check_not_observer(self.request.user)
        instance.delete()


# ── Lot-entry submission ──────────────────────────────────────────────────────

class WorkItemEntryView(APIView):
    """
    GET  /api/update-work/items/<item_id>/entries/  – list all entries for an item
    POST /api/update-work/items/<item_id>/entries/  – submit a new lot entry
    """

    def get(self, request, item_id):
        entries = WorkItemEntry.objects.filter(work_item_id=item_id).order_by('-submitted_at')
        serializer = WorkItemEntrySerializer(entries, many=True)
        return Response(serializer.data)

    def post(self, request, item_id):
        _check_not_observer(request.user)

        try:
            work_item = WorkItem.objects.get(pk=item_id)
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

        entry = WorkItemEntry.objects.create(
            work_item=work_item,
            quantity=qty,
            challan_no=request.data.get('challan_no', '') or '',
            udm_entry=request.data.get('udm_entry', '') or '',
            submitted_by=request.user if request.user.is_authenticated else None,
        )

        # Keep WorkItem.supplied_quantity in sync (used by dashboard)
        total = WorkItemEntry.objects.filter(work_item=work_item).aggregate(
            total=Sum('quantity')
        )['total'] or 0
        work_item.supplied_quantity = total
        work_item.save(update_fields=['supplied_quantity'])

        serializer = WorkItemEntrySerializer(entry)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
