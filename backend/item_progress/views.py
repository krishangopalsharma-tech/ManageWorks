from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.db.models import Q, F, Case, When, FloatField, Sum, Count
from django.db.models.functions import Length, Upper, Trim, Least, Round
from works.models import Work, WorkItem
from works.utils import contractor_nickname as _nickname, can_see_all_entries
from works.pagination import ProgressPageNumberPagination
from .serializers import ItemProgressItemSerializer

# The 3 categories this page filters by — "all 3 selected" is treated the
# same as "no category filter", matching the frontend's own skip-if-all check.
ALL_CATEGORIES = ('supply', 'supply_installation', 'execution')


class WorkListView(APIView):
    """GET /api/item-progress/works/ — lightweight work list for the dropdown."""

    def get(self, request):
        if not request.user.is_authenticated:
            return Response({'error': 'Login required.'}, status=status.HTTP_401_UNAUTHORIZED)
        works = Work.objects.values('id', 'loa_number', 'tender_number', 'contractor_name')
        data = [dict(w, contractor_nickname=_nickname(w['contractor_name'] or '')) for w in works]
        return Response(data)


def _empty_page_response():
    paginator = ProgressPageNumberPagination()
    resp = Response({'count': 0, 'next': None, 'previous': None, 'results': []})
    resp.data['stats'] = {'supplyPct': 0, 'execPct': 0, 'supplyCount': 0, 'execCount': 0}
    return resp


def _compute_stats(queryset):
    """Mirrors the frontend's `stats` computed in ItemProgress.vue: category-first,
    schedule-fallback split into Supply vs Execution+S+I, summed over the FULL
    filtered set (not just the current page)."""
    no_cat = Q(category__isnull=True) | Q(category='')
    supply_cond = Q(category='supply') | (no_cat & Q(schedule_norm__startswith='A'))
    exec_cond = Q(category__in=['execution', 'supply_installation']) | (no_cat & Q(schedule_norm__startswith='B'))

    agg = queryset.aggregate(
        supply_total=Sum('qty', filter=supply_cond),
        supply_done=Sum('supplied_quantity', filter=supply_cond),
        supply_count=Count('id', filter=supply_cond),
        exec_total=Sum('qty', filter=exec_cond),
        exec_done=Sum('executed_quantity', filter=exec_cond),
        exec_count=Count('id', filter=exec_cond),
    )

    def pct(done, total):
        return round((done or 0) / total * 100) if total else 0

    return {
        'supplyPct': pct(agg['supply_done'], agg['supply_total']),
        'execPct': pct(agg['exec_done'], agg['exec_total']),
        'supplyCount': agg['supply_count'] or 0,
        'execCount': agg['exec_count'] or 0,
    }


class ItemSearchView(APIView):
    """
    GET /api/item-progress/search/
    Query params:
      work_ids        comma-separated Work ids
      q               free text — matches item_desc / schedule / serial_number / LOA number
      category        comma-separated subset of supply,supply_installation,execution
                      (omitted or all 3 = no filter)
      progress_min/max, include_excess   mirrors the on-page progress-range slider
      ordering        qty | submitted | remaining | progress | entries, prefix "-" for desc
      page, page_size standard DRF pagination params

    Response: {count, next, previous, results, stats}
    """

    def get(self, request):
        if not request.user.is_authenticated:
            return Response({'error': 'Login required.'}, status=status.HTTP_401_UNAUTHORIZED)

        q              = request.query_params.get('q', '').strip()
        work_ids_param = request.query_params.get('work_ids', '').strip()

        if not q and not work_ids_param:
            return _empty_page_response()

        queryset = (
            WorkItem.objects
            .select_related('work')
            .prefetch_related('entries__submitted_by__profile')
        )

        if work_ids_param:
            try:
                ids = [int(i) for i in work_ids_param.split(',') if i.strip()]
                queryset = queryset.filter(work_id__in=ids)
            except ValueError:
                pass

        if q:
            queryset = queryset.filter(
                Q(item_desc__icontains=q) |
                Q(schedule__icontains=q) |
                Q(serial_number__icontains=q) |
                Q(work__loa_number__icontains=q)
            )

        # Category pill filter — matches the frontend's `item.category || 'supply'`
        # exactly: an uncategorized item defaults to 'supply' for THIS filter only
        # (unlike the schedule-based fallback used for progress/stats below).
        category_param = request.query_params.get('category')
        if category_param is not None:
            categories = [c for c in category_param.split(',') if c]
            if len(categories) < len(ALL_CATEGORIES):
                cat_cond = Q(category__in=categories)
                if 'supply' in categories:
                    cat_cond |= Q(category__isnull=True) | Q(category='')
                queryset = queryset.filter(cat_cond)

        # Annotate done/progress/remaining using the same category-first,
        # schedule-fallback logic as the frontend's progressPct()/suppliedOrExecuted().
        queryset = queryset.annotate(schedule_norm=Upper(Trim('schedule')))
        done_expr = Case(
            When(category__in=['supply_installation', 'execution'], then=F('executed_quantity')),
            When(category='supply', then=F('supplied_quantity')),
            When(schedule_norm__startswith='B', then=F('executed_quantity')),
            default=F('supplied_quantity'),
            output_field=FloatField(),
        )
        queryset = queryset.annotate(done_qty=done_expr)
        queryset = queryset.annotate(
            progress_pct_calc=Case(
                When(qty__gt=0, then=Least(Round(F('done_qty') / F('qty') * 100.0), 999.0)),
                default=0.0,
                output_field=FloatField(),
            ),
            remaining_qty=F('qty') - F('done_qty'),
            entries_count=Count('entries'),
        )

        # Progress-range filter — mirrors the frontend exactly: an item over 100%
        # only passes if "include excess" is on; otherwise it must sit in [min, max].
        progress_min_raw = request.query_params.get('progress_min')
        progress_max_raw = request.query_params.get('progress_max')
        include_excess = request.query_params.get('include_excess', 'true').lower() != 'false'
        try:
            pmin = float(progress_min_raw) if progress_min_raw is not None else 0.0
        except ValueError:
            pmin = 0.0
        try:
            pmax = float(progress_max_raw) if progress_max_raw is not None else 100.0
        except ValueError:
            pmax = 100.0

        if pmin > 0 or pmax < 100 or not include_excess:
            in_range = Q(progress_pct_calc__gte=pmin, progress_pct_calc__lte=pmax)
            excess = Q(progress_pct_calc__gt=100) if include_excess else Q(pk__in=[])
            queryset = queryset.filter(in_range | excess)

        # Ordering
        ORDER_MAP = {
            'qty': 'qty',
            'submitted': 'done_qty',
            'remaining': 'remaining_qty',
            'progress': 'progress_pct_calc',
            'entries': 'entries_count',
        }
        order_fields = ['work_id', 'schedule', Length('serial_number'), 'serial_number', 'id']
        ordering_param = request.query_params.get('ordering', '').strip()
        if ordering_param:
            desc = ordering_param.startswith('-')
            key = ordering_param[1:] if desc else ordering_param
            field = ORDER_MAP.get(key)
            if field:
                order_fields = [f'-{field}' if desc else field, 'id']
        queryset = queryset.order_by(*order_fields)

        # Stats over the full filtered (pre-pagination) set — must stay accurate
        # even though the client only ever holds one page of results at a time.
        stats = _compute_stats(queryset)

        paginator = ProgressPageNumberPagination()
        page = paginator.paginate_queryset(queryset, request)
        if page is None:
            page = []

        data = []
        for item in page:
            serialized = ItemProgressItemSerializer(item).data
            serialized['loa_number'] = item.work.loa_number or '—'
            serialized['contractor_name'] = item.work.contractor_name or '—'
            serialized['contractor_nickname'] = _nickname(item.work.contractor_name or '')
            serialized['tender_number'] = item.work.tender_number or '—'
            # Privacy: non-assigned consignees see cumulative totals but only their own entries
            if not can_see_all_entries(request.user, item.work):
                serialized['entries'] = [
                    e for e in serialized.get('entries', [])
                    if e.get('submitted_by') == request.user.id
                ]
            data.append(serialized)

        resp = paginator.get_paginated_response(data)
        resp.data['stats'] = stats
        return resp
