from django.db.models import Q, Sum
from django.db.models.functions import TruncDay, TruncWeek, TruncMonth, TruncYear
from django.utils import timezone
from datetime import timedelta
from rest_framework.views import APIView
from rest_framework.response import Response
from works.models import Work, WorkItem, WorkItemEntry
from mb_details.models import MBItem


class DashboardStatsView(APIView):
    def get(self, request):
        loa_id = request.query_params.get('loa_id')

        if loa_id:
            items = WorkItem.objects.filter(work_id=loa_id)
        else:
            items = WorkItem.objects.all()

        supply_progress_sum = 0
        supply_count = 0
        exec_progress_sum = 0
        exec_count = 0

        for item in items:
            q   = item.qty or 0
            sch = str(item.schedule).upper().strip() if item.schedule else ''

            if sch.startswith('A'):
                sq          = item.supplied_quantity or 0
                item_prog   = (sq / q) if q > 0 else 0
                supply_progress_sum += item_prog
                supply_count        += 1
            elif sch.startswith('B'):
                # For supply-and-install items, progress is execution (installed), not supply delivered
                eq        = item.executed_quantity or 0
                item_prog = (eq / q) if q > 0 else 0
                exec_progress_sum += item_prog
                exec_count        += 1

        supply_avg  = (supply_progress_sum / supply_count * 100) if supply_count > 0 else 0
        exec_avg    = (exec_progress_sum   / exec_count   * 100) if exec_count   > 0 else 0
        overall_cnt = supply_count + exec_count
        overall_avg = ((supply_progress_sum + exec_progress_sum) / overall_cnt * 100) if overall_cnt > 0 else 0

        # Financial progress — sourced from MB items
        if loa_id:
            total_work_amount = WorkItem.objects.filter(work_id=loa_id).aggregate(t=Sum('total_amount'))['t'] or 0
            mb_total          = MBItem.objects.filter(mb_record__work_id=loa_id).aggregate(t=Sum('amount'))['t'] or 0
        else:
            total_work_amount = WorkItem.objects.aggregate(t=Sum('total_amount'))['t'] or 0
            mb_total          = MBItem.objects.aggregate(t=Sum('amount'))['t'] or 0

        fin_prog = (mb_total / total_work_amount * 100) if total_work_amount > 0 else 0

        loa_list = [
            {
                'id':    w.id,
                'label': f"{w.tender_number or 'Unknown Tender'} | {w.loa_number or 'Unknown LOA'} | {w.contractor_name or 'Unknown'}"
            }
            for w in Work.objects.all()
        ]

        return Response({
            'supply':    round(supply_avg,  2),
            'execution': round(exec_avg,    2),
            'overall':   round(overall_avg, 2),
            'financial': round(fin_prog,    2),
            'loas':      loa_list,
        })


class ProgressTrendView(APIView):
    """
    GET /api/dashboard/trend/?period=daily|weekly|monthly|yearly&loa_id=<id>
    Only counts entries that contribute to progress:
      - supply entries for Schedule-A items
      - execution entries for Schedule-B items
    """

    PERIOD_CONFIG = {
        'daily':   {'trunc': TruncDay,   'fmt': '%d %b',  'cutoff_days': 30},
        'weekly':  {'trunc': TruncWeek,  'fmt': 'W%V %y', 'cutoff_days': 84},
        'monthly': {'trunc': TruncMonth, 'fmt': '%b %Y',  'cutoff_days': 365},
        'yearly':  {'trunc': TruncYear,  'fmt': '%Y',     'cutoff_days': None},
    }

    def get(self, request):
        period = request.query_params.get('period', 'monthly')
        loa_id = request.query_params.get('loa_id')

        cfg = self.PERIOD_CONFIG.get(period, self.PERIOD_CONFIG['monthly'])

        item_qs        = WorkItem.objects.filter(work_id=loa_id) if loa_id else WorkItem.objects.all()
        total_required = item_qs.aggregate(t=Sum('qty'))['t'] or 0

        # Only count progress-relevant entries
        entries = WorkItemEntry.objects.filter(
            Q(work_item__schedule__istartswith='A', entry_type='supply') |
            Q(work_item__schedule__istartswith='B', entry_type='execution')
        )
        if loa_id:
            entries = entries.filter(work_item__work_id=loa_id)
        if cfg['cutoff_days']:
            cutoff  = timezone.now() - timedelta(days=cfg['cutoff_days'])
            entries = entries.filter(submitted_at__gte=cutoff)

        rows = (
            entries
            .annotate(bucket=cfg['trunc']('submitted_at'))
            .values('bucket')
            .annotate(total=Sum('quantity'))
            .order_by('bucket')
        )

        data = []
        for row in rows:
            if row['bucket'] is None:
                continue
            qty = row['total'] or 0
            pct = round(qty / total_required * 100, 2) if total_required > 0 else 0
            data.append({'label': row['bucket'].strftime(cfg['fmt']), 'value': pct})

        return Response(data)
