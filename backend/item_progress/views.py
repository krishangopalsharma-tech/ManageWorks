from rest_framework.views import APIView
from rest_framework.response import Response
from django.db.models import Q
from works.models import Work, WorkItem
from works.serializers import WorkItemSerializer


class WorkListView(APIView):
    """GET /api/item-progress/works/ — lightweight work list for the dropdown."""

    def get(self, _request):
        works = Work.objects.values('id', 'loa_number', 'tender_number', 'contractor_name')
        return Response(list(works))


class ItemSearchView(APIView):
    """
    GET /api/item-progress/search/?q=cable&work_ids=1,2,3
    Returns WorkItems matching the query, optionally filtered to specific works.
    At least one character in `q` is required to prevent returning all items.
    """

    def get(self, request):
        q = request.query_params.get('q', '').strip()
        if not q:
            return Response([])

        work_ids_param = request.query_params.get('work_ids', '')
        queryset = WorkItem.objects.select_related('work').prefetch_related('entries__submitted_by__profile')

        if work_ids_param:
            try:
                ids = [int(i) for i in work_ids_param.split(',') if i.strip()]
                queryset = queryset.filter(work_id__in=ids)
            except ValueError:
                pass

        queryset = queryset.filter(
            Q(item_desc__icontains=q) |
            Q(schedule__icontains=q) |
            Q(serial_number__icontains=q)
        )

        data = []
        for item in queryset:
            serialized = WorkItemSerializer(item).data
            serialized['loa_number']      = item.work.loa_number or '—'
            serialized['contractor_name'] = item.work.contractor_name or '—'
            data.append(serialized)

        return Response(data)
