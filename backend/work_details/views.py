from rest_framework import generics, status
from rest_framework.response import Response
from django.db.models import Q, Prefetch
from django.db.models.functions import Length
from works.models import Work, WorkItem
from works.serializers import WorkSerializer
from works.utils import can_see_all_entries


def _items_queryset():
    return WorkItem.objects.prefetch_related(
        'entries__submitted_by__profile',
        'updated_by__profile',
    ).order_by('schedule', Length('serial_number'), 'serial_number', 'id')


def _base_queryset():
    return Work.objects.prefetch_related(
        Prefetch('items', queryset=_items_queryset()),
        'extensions',
        'bill_records__items',
    )


class WorkSearchView(generics.ListAPIView):
    """
    List/search all LOAs — every authenticated user sees the full list (progress-view).
    Full entry-level detail (who submitted what) is restricted per-LOA in WorkRetrieveView.
    """
    serializer_class = WorkSerializer

    def list(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return Response({'error': 'Login required.'}, status=status.HTTP_401_UNAUTHORIZED)
        return super().list(request, *args, **kwargs)

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


class WorkRetrieveView(generics.RetrieveAPIView):
    """
    Any authenticated user can open any LOA's record. Admin/Super Admin and the LOA's
    assigned consignee see every entry; everyone else sees item/progress data but only
    their own submitted entries (matches the privacy model already used by Item/Location
    Progress via works.utils.can_see_all_entries).
    """
    serializer_class = WorkSerializer

    def retrieve(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return Response({'error': 'Login required.'}, status=status.HTTP_401_UNAUTHORIZED)
        instance = self.get_object()
        data = self.get_serializer(instance).data
        if not can_see_all_entries(request.user, instance):
            for item in data.get('items', []):
                item['entries'] = [
                    e for e in item.get('entries', [])
                    if e.get('submitted_by') == request.user.id
                ]
        return Response(data)

    def get_queryset(self):
        return _base_queryset()
