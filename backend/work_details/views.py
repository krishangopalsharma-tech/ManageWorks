from rest_framework import generics, status
from rest_framework.response import Response
from django.db.models import Q, Prefetch
from django.db.models.functions import Length
from works.models import Work, WorkItem
from works.serializers import WorkSerializer
from works.utils import can_see_all_entries, redact_financials


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
    List/search all LOAs — every authenticated user sees the full list. The
    frontend's Work Details page renders its per-LOA detail view straight from
    this response (it never calls WorkRetrieveView), so the same per-LOA
    privacy rules from there are applied per-row here too: Admin/Super Admin
    and each LOA's own assigned consignee see every entry and full contract/
    billing fields; everyone else gets their own entries only and no contract-
    identity/billing fields, on a per-LOA basis (own LOA vs. everyone else's).
    """
    serializer_class = WorkSerializer

    def list(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return Response({'error': 'Login required.'}, status=status.HTTP_401_UNAUTHORIZED)
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        target = list(page if page is not None else queryset)
        data = self.get_serializer(target, many=True).data
        user = request.user
        for work_instance, row in zip(target, data):
            if not can_see_all_entries(user, work_instance):
                for item in row.get('items') or []:
                    item['entries'] = [
                        e for e in item.get('entries', [])
                        if e.get('submitted_by') == user.id
                    ]
                redact_financials(row)
        if page is not None:
            return self.get_paginated_response(data)
        return Response(data)

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
    assigned consignee see full detail, every entry; everyone else gets progress-view
    only — item/progress data, their own submitted entries, and no financial fields
    (matches the privacy model already used by Item/Location Progress via
    works.utils.can_see_all_entries).
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
            data = redact_financials(data)
        return Response(data)

    def get_queryset(self):
        return _base_queryset()
