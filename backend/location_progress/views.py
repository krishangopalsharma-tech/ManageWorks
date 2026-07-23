from collections import defaultdict

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.db.models import Q, F, Case, When, FloatField, Max, Sum, Count
from django.db.models.functions import Upper, Trim, Least, Round

from works.models import Work, WorkItem, WorkItemEntry
from works.utils import contractor_nickname as _nickname, can_see_all_entries
from works.pagination import ProgressPageNumberPagination

# The 2 categories this page filters by (S+I and Execution only) — "both
# selected" is treated the same as "no category filter".
ALL_CATEGORIES = ('supply_installation', 'execution')


class WorkListView(APIView):
    def get(self, request):
        if not request.user.is_authenticated:
            return Response({'error': 'Login required.'}, status=status.HTTP_401_UNAUTHORIZED)
        works = Work.objects.values('id', 'loa_number', 'tender_number', 'contractor_name')
        data = [dict(w, contractor_nickname=_nickname(w['contractor_name'] or '')) for w in works]
        return Response(data)


def _base_entry_queryset():
    return (
        WorkItemEntry.objects
        .filter(entry_type='execution')
        .exclude(location__isnull=True)
        .exclude(location='')
        .annotate(location_norm=Upper(Trim('location')))
    )


def _compute_stats(grouped_qs):
    """Mirrors the frontend's `stats` computed in LocationProgress.vue — counts
    over the full filtered set of (location, item) groups, not just one page.
    Uses separate .count() calls (rather than a single .aggregate()) since
    grouped_qs is itself a values().annotate() queryset — counting a further
    filtered version of it is the well-supported pattern; aggregating multiple
    conditions in one .aggregate() call on top of an existing GROUP BY is not."""
    return {
        'sections': grouped_qs.filter(location_norm__contains='-').count(),
        'stations': grouped_qs.exclude(location_norm__contains='-').count(),
        'siCount': grouped_qs.filter(work_item__category='supply_installation').count(),
        'exCount': grouped_qs.filter(work_item__category='execution').count(),
    }


class LocationProgressView(APIView):
    """
    GET /api/location-progress/data/
    Returns one row per (location, work_item) pair that has execution entries.
    Query params:
      work_ids   comma-separated Work ids
      category   comma-separated subset of supply_installation,execution
      q          free text — matches item_desc / schedule / serial_number
      location   free text — matches location (case-insensitive substring)
      ordering   location | executed | scope | remaining | progress | entries,
                 prefix "-" for desc
      page, page_size   standard DRF pagination params

    Privacy: admin and assigned consignee see all entries in the detail panel;
    other consignees see cumulative totals but only their own entries.

    Response: {count, next, previous, results, stats}
    """

    def get(self, request):
        if not request.user.is_authenticated:
            return Response({'error': 'Login required.'}, status=status.HTTP_401_UNAUTHORIZED)

        work_ids_param = request.query_params.get('work_ids', '').strip()
        q = request.query_params.get('q', '').strip()
        location_q = request.query_params.get('location', '').strip().upper()

        base = _base_entry_queryset()

        if work_ids_param:
            ids = [int(x) for x in work_ids_param.split(',') if x.strip().isdigit()]
            if ids:
                base = base.filter(work_item__work_id__in=ids)

        # Category pill filter — matches the frontend's `r.category || 'supply'`
        # exactly: an uncategorized item defaults to 'supply' for this filter
        # (there's no "Supply" pill on this page, so an uncategorized item only
        # ever matches when 'supply' happens to be in the requested list).
        category_param = request.query_params.get('category')
        if category_param is not None:
            categories = [c for c in category_param.split(',') if c]
            if len(categories) < len(ALL_CATEGORIES):
                cat_cond = Q(work_item__category__in=categories)
                if 'supply' in categories:
                    cat_cond |= Q(work_item__category__isnull=True) | Q(work_item__category='')
                base = base.filter(cat_cond)

        if q:
            base = base.filter(
                Q(work_item__item_desc__icontains=q) |
                Q(work_item__serial_number__icontains=q) |
                Q(work_item__schedule__icontains=q)
            )

        if location_q:
            base = base.filter(location_norm__icontains=location_q)

        # Group by (location, work_item) — one row per bucket, matching the
        # old in-Python defaultdict grouping but done at the DB level so it
        # can be paginated. scope/total_executed pull in the WorkItem's own
        # fields via Max() (constant per group) rather than a bare F() ref,
        # since Postgres requires joined non-aggregate columns in a grouped
        # query to be wrapped in an aggregate.
        grouped = (
            base.values('location_norm', 'work_item_id')
            .annotate(
                executed_here=Sum('quantity'),
                entries_count=Count('id'),
                scope=Max('work_item__qty'),
                total_executed=Max('work_item__executed_quantity'),
            )
        )
        grouped = grouped.annotate(
            remaining=F('scope') - F('total_executed'),
            progress_pct=Case(
                When(scope__gt=0, then=Least(Round(F('total_executed') / F('scope') * 100.0), 999.0)),
                default=0.0,
                output_field=FloatField(),
            ),
        )

        ORDER_MAP = {
            'executed': 'executed_here',
            'scope': 'scope',
            'remaining': 'remaining',
            'progress': 'progress_pct',
            'entries': 'entries_count',
            'location': 'location_norm',
        }
        order_fields = ['location_norm', 'work_item_id']
        ordering_param = request.query_params.get('ordering', '').strip()
        if ordering_param:
            desc = ordering_param.startswith('-')
            key = ordering_param[1:] if desc else ordering_param
            field = ORDER_MAP.get(key)
            if field:
                order_fields = [f'-{field}' if desc else field, 'work_item_id']
        grouped = grouped.order_by(*order_fields)

        stats = _compute_stats(grouped)

        paginator = ProgressPageNumberPagination()
        page = paginator.paginate_queryset(grouped, request)
        if page is None:
            page = []

        wi_ids = list({row['work_item_id'] for row in page})
        items_by_id = {
            wi.id: wi for wi in
            WorkItem.objects.select_related('work').filter(id__in=wi_ids)
        }

        page_keys = [(row['location_norm'], row['work_item_id']) for row in page]
        entries_by_key = defaultdict(list)
        if page_keys:
            entries_filter = Q()
            for loc, wi_id in page_keys:
                entries_filter |= Q(location_norm=loc, work_item_id=wi_id)
            raw_entries = (
                base.filter(entries_filter)
                .select_related('submitted_by', 'submitted_by__profile')
                .order_by('submitted_at')
            )
            for e in raw_entries:
                entries_by_key[(e.location_norm, e.work_item_id)].append(e)

        result = []
        for row in page:
            key = (row['location_norm'], row['work_item_id'])
            wi = items_by_id.get(row['work_item_id'])
            if not wi:
                continue
            work = wi.work
            loc = row['location_norm']

            full_access = can_see_all_entries(request.user, work)
            bucket_entries = entries_by_key.get(key, [])
            visible_entries = bucket_entries if full_access else [
                e for e in bucket_entries if e.submitted_by_id == request.user.id
            ]

            entries_out = []
            for e in visible_entries:
                user_obj = e.submitted_by
                full_name = ''
                designation = e.submitted_by_designation or ''
                if user_obj:
                    full_name = f"{user_obj.first_name} {user_obj.last_name}".strip() or user_obj.username
                    if not designation:
                        try:
                            designation = user_obj.profile.designation
                        except Exception:
                            pass
                entries_out.append({
                    'id': e.id,
                    'quantity': e.quantity,
                    'submitted_at': e.submitted_at.isoformat() if e.submitted_at else None,
                    'submitted_by_name': full_name,
                    'submitted_by_designation': designation,
                    'remarks': e.remarks or '',
                })

            result.append({
                'location': loc,
                'location_type': 'section' if '-' in loc else 'station',
                'work_id': work.id,
                'work_item_id': wi.id,
                'serial_number': wi.serial_number or '',
                'schedule': wi.schedule or '',
                'category': wi.category or '',
                'item_desc': wi.item_desc or '',
                'unit': wi.unit or '',
                'scope': row['scope'] or 0,
                'executed_here': round(row['executed_here'] or 0, 3),
                'total_executed': row['total_executed'] or 0,
                'remaining': round(row['remaining'] or 0, 3),
                'progress_pct': row['progress_pct'],
                'entries_count': row['entries_count'],
                'visible_entries_count': len(entries_out),
                'loa_number': work.loa_number or '',
                'tender_number': work.tender_number or '',
                'contractor_name': work.contractor_name or '',
                'contractor_nickname': _nickname(work.contractor_name or ''),
                'entries': entries_out,
            })

        resp = paginator.get_paginated_response(result)
        resp.data['stats'] = stats
        return resp
