from rest_framework import generics, status
from rest_framework.response import Response
from django.db.models import Q, Prefetch
from django.db.models.functions import Length
from works.models import Work, WorkItem
from works.serializers import WorkSerializer
from works.utils import is_admin_user


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

    def list(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return Response({'error': 'Login required.'}, status=status.HTTP_401_UNAUTHORIZED)
        return super().list(request, *args, **kwargs)

    def get_queryset(self):
        queryset = _base_queryset()
        if not is_admin_user(self.request.user):
            queryset = queryset.filter(hrms_id=self.request.user.username)
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

    def retrieve(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return Response({'error': 'Login required.'}, status=status.HTTP_401_UNAUTHORIZED)
        return super().retrieve(request, *args, **kwargs)

    def get_queryset(self):
        queryset = _base_queryset()
        if not is_admin_user(self.request.user):
            queryset = queryset.filter(hrms_id=self.request.user.username)
        return queryset
