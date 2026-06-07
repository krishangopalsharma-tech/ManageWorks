from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from collections import defaultdict
from works.models import Work, WorkItemEntry
from works.utils import contractor_nickname as _nickname, can_see_all_entries


class WorkListView(APIView):
    def get(self, request):
        if not request.user.is_authenticated:
            return Response({'error': 'Login required.'}, status=status.HTTP_401_UNAUTHORIZED)
        works = Work.objects.values('id', 'loa_number', 'tender_number', 'contractor_name')
        data = [dict(w, contractor_nickname=_nickname(w['contractor_name'] or '')) for w in works]
        return Response(data)


class LocationProgressView(APIView):
    """
    Returns one row per (location, work_item) pair that has execution entries.
    Privacy: admin and assigned consignee see all entries in the detail panel;
    other consignees see cumulative totals but only their own entries.
    """

    def get(self, request):
        if not request.user.is_authenticated:
            return Response({'error': 'Login required.'}, status=status.HTTP_401_UNAUTHORIZED)

        work_ids_param = request.query_params.get('work_ids', '')

        qs = (
            WorkItemEntry.objects
            .filter(entry_type='execution')
            .exclude(location__isnull=True)
            .exclude(location='')
            .select_related('work_item', 'work_item__work', 'submitted_by', 'submitted_by__profile')
            .order_by('work_item__work_id', 'work_item_id', 'submitted_at')
        )

        if work_ids_param:
            ids = [int(x) for x in work_ids_param.split(',') if x.strip().isdigit()]
            if ids:
                qs = qs.filter(work_item__work_id__in=ids)

        # Group by (normalised_location, work_item_id)
        # Key: (location_upper, work_item_id)
        bucket_map = defaultdict(lambda: {
            'executed_here': 0.0,
            'entries': [],
            '_wi': None,
        })

        for entry in qs:
            loc = (entry.location or '').strip().upper()
            if not loc:
                continue
            key = (loc, entry.work_item_id)
            b = bucket_map[key]
            b['executed_here'] += entry.quantity or 0
            b['entries'].append(entry)
            b['_wi'] = entry.work_item

        result = []
        for (loc, wi_id), b in sorted(bucket_map.items(), key=lambda x: (x[0][0], x[0][1])):
            wi   = b['_wi']
            work = wi.work
            scope         = wi.qty or 0
            total_exec    = wi.executed_quantity or 0
            remaining     = scope - total_exec
            progress_pct  = round(total_exec / scope * 100, 1) if scope else 0

            # Build entry list — apply privacy filter
            full_access = can_see_all_entries(request.user, work)
            visible_entries = b['entries'] if full_access else [
                e for e in b['entries'] if e.submitted_by_id == request.user.id
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
                    'id':           e.id,
                    'quantity':     e.quantity,
                    'submitted_at': e.submitted_at.isoformat() if e.submitted_at else None,
                    'submitted_by_name':        full_name,
                    'submitted_by_designation': designation,
                    'remarks':      e.remarks or '',
                })

            result.append({
                'location':          loc,
                'location_type':     'section' if '-' in loc else 'station',
                'work_id':           work.id,
                'work_item_id':      wi.id,
                'serial_number':     wi.serial_number or '',
                'schedule':          wi.schedule or '',
                'category':          wi.category or '',
                'item_desc':         wi.item_desc or '',
                'unit':              wi.unit or '',
                'scope':             scope,
                'executed_here':     round(b['executed_here'], 3),
                'total_executed':    round(total_exec, 3),
                'remaining':         round(remaining, 3),
                'progress_pct':      progress_pct,
                'entries_count':     len(b['entries']),     # always full count (cumulative)
                'visible_entries_count': len(entries_out),  # what this user can see
                'loa_number':        work.loa_number or '',
                'tender_number':     work.tender_number or '',
                'contractor_name':   work.contractor_name or '',
                'contractor_nickname': _nickname(work.contractor_name or ''),
                'entries':           entries_out,
            })

        return Response(result)
