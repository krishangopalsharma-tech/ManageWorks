from rest_framework import generics
from django.db.models import Q, Prefetch
from django.db.models.functions import Length
from works.models import Work, WorkItem
from works.serializers import WorkSerializer


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


class WorkRetrieveView(generics.RetrieveAPIView):
    serializer_class = WorkSerializer
    queryset = _base_queryset()
