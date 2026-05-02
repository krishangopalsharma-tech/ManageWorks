from django.db.models import Q, Sum
from django.db.models.functions import TruncDay, TruncWeek, TruncMonth, TruncYear
from django.utils import timezone
from datetime import timedelta
from rest_framework.views import APIView
from rest_framework.response import Response
from works.models import Work, WorkItem, WorkItemEntry
from mb_details.models import MBItem, MBRecord


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

        item_qs   = WorkItem.objects.filter(work_id=loa_id) if loa_id else WorkItem.objects.all()
        sch_a_qty = item_qs.filter(schedule__istartswith='A').aggregate(t=Sum('qty'))['t'] or 0
        sch_b_qty = item_qs.filter(schedule__istartswith='B').aggregate(t=Sum('qty'))['t'] or 0

        cutoff = timezone.now() - timedelta(days=cfg['cutoff_days']) if cfg['cutoff_days'] else None

        supply_qs = WorkItemEntry.objects.filter(
            work_item__schedule__istartswith='A', entry_type='supply'
        )
        exec_qs = WorkItemEntry.objects.filter(
            work_item__schedule__istartswith='B', entry_type='execution'
        )
        if loa_id:
            supply_qs = supply_qs.filter(work_item__work_id=loa_id)
            exec_qs   = exec_qs.filter(work_item__work_id=loa_id)

        supply_totals = {}
        exec_totals   = {}

        def _acc(rows, bucket_dict):
            for row in rows:
                bucket = row['bucket']
                if bucket is None:
                    continue
                sort_key = bucket.date() if hasattr(bucket, 'date') and callable(bucket.date) else bucket
                bucket_dict[sort_key] = bucket_dict.get(sort_key, 0) + (row['total'] or 0)

        # Supply with date_of_receipt
        sq_with = supply_qs.filter(date_of_receipt__isnull=False)
        if cutoff:
            sq_with = sq_with.filter(date_of_receipt__gte=cutoff.date())
        _acc(sq_with.annotate(bucket=cfg['trunc']('date_of_receipt'))
             .values('bucket').annotate(total=Sum('quantity')), supply_totals)

        # Supply without date_of_receipt → fall back to submitted_at
        sq_without = supply_qs.filter(date_of_receipt__isnull=True)
        if cutoff:
            sq_without = sq_without.filter(submitted_at__gte=cutoff)
        _acc(sq_without.annotate(bucket=cfg['trunc']('submitted_at'))
             .values('bucket').annotate(total=Sum('quantity')), supply_totals)

        # Execution
        eq = exec_qs.filter(submitted_at__gte=cutoff) if cutoff else exec_qs
        _acc(eq.annotate(bucket=cfg['trunc']('submitted_at'))
             .values('bucket').annotate(total=Sum('quantity')), exec_totals)

        # Financial: MB items grouped by MB record's measurement_date
        total_work_amount = item_qs.aggregate(t=Sum('total_amount'))['t'] or 0
        fin_totals = {}
        mb_qs = MBItem.objects.filter(mb_record__measurement_date__isnull=False)
        if loa_id:
            mb_qs = mb_qs.filter(mb_record__work_id=loa_id)
        if cutoff:
            mb_qs = mb_qs.filter(mb_record__measurement_date__gte=cutoff.date())
        for row in (mb_qs
                    .annotate(bucket=cfg['trunc']('mb_record__measurement_date'))
                    .values('bucket').annotate(total=Sum('amount'))):
            if row['bucket'] is None:
                continue
            k = row['bucket'].date() if hasattr(row['bucket'], 'date') and callable(row['bucket'].date) else row['bucket']
            fin_totals[k] = fin_totals.get(k, 0) + (row['total'] or 0)

        all_keys = sorted(supply_totals.keys() | exec_totals.keys() | fin_totals.keys())
        data = []
        for k in all_keys:
            s_qty = supply_totals.get(k, 0)
            e_qty = exec_totals.get(k, 0)
            f_amt = fin_totals.get(k, 0)
            data.append({
                'label':     k.strftime(cfg['fmt']),
                'supply':    round(s_qty / sch_a_qty * 100, 2) if sch_a_qty else 0,
                'execution': round(e_qty / sch_b_qty * 100, 2) if sch_b_qty else 0,
                'financial': round(f_amt / total_work_amount * 100, 2) if total_work_amount else 0,
            })

        return Response(data)
