from django.db.models import Q, Sum
from django.db.models.functions import TruncDay, TruncWeek, TruncMonth, TruncYear
from django.utils import timezone
from datetime import timedelta
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from works.models import Work, WorkItem, WorkItemEntry
from works.utils import contractor_nickname as _nickname
from financial_progress.models import BillItem


class DashboardStatsView(APIView):
    def get(self, request):
        if not request.user.is_authenticated:
            return Response({'error': 'Login required.'}, status=status.HTTP_401_UNAUTHORIZED)
        loa_ids_param = request.query_params.get('loa_ids')
        loa_id = request.query_params.get('loa_id')

        if loa_ids_param:
            ids = [int(x) for x in loa_ids_param.split(',') if x.strip().isdigit()]
            items = WorkItem.objects.filter(work_id__in=ids)
        elif loa_id:
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

        # Financial progress — sourced from bill items (latest per item, cumulative amt_total)
        if loa_ids_param and ids:
            total_work_amount = WorkItem.objects.filter(work_id__in=ids).aggregate(t=Sum('total_amount'))['t'] or 0
            bill_items = BillItem.objects.filter(bill_record__work_id__in=ids).select_related('bill_record').order_by('schedule_name', 'item_number', '-bill_record__bill_date', '-bill_record__id')
        elif loa_id:
            total_work_amount = WorkItem.objects.filter(work_id=loa_id).aggregate(t=Sum('total_amount'))['t'] or 0
            bill_items = BillItem.objects.filter(bill_record__work_id=loa_id).select_related('bill_record').order_by('schedule_name', 'item_number', '-bill_record__bill_date', '-bill_record__id')
        else:
            total_work_amount = WorkItem.objects.aggregate(t=Sum('total_amount'))['t'] or 0
            bill_items = BillItem.objects.all().select_related('bill_record').order_by('schedule_name', 'item_number', '-bill_record__bill_date', '-bill_record__id')

        seen = set()
        bill_total = 0
        for item in bill_items:
            key = (item.bill_record.work_id, item.schedule_name, item.item_number)
            if key not in seen:
                seen.add(key)
                bill_total += (item.amt_total or 0)

        fin_prog = (bill_total / total_work_amount * 100) if total_work_amount > 0 else 0

        recent_cutoff = timezone.now() - timedelta(days=7)
        recent_supply_ids = set(
            WorkItemEntry.objects.filter(entry_type='supply', submitted_at__gte=recent_cutoff)
            .values_list('work_item__work_id', flat=True).distinct()
        )
        recent_exec_ids = set(
            WorkItemEntry.objects.filter(entry_type='execution', submitted_at__gte=recent_cutoff)
            .values_list('work_item__work_id', flat=True).distinct()
        )

        loa_list = [
            {
                'id':                  w.id,
                'label':               f"{w.tender_number or 'Unknown Tender'} | {w.loa_number or 'Unknown LOA'} | {w.contractor_name or 'Unknown'}",
                'contractor_nickname': _nickname(w.contractor_name or ''),
                'supply_update':       w.id in recent_supply_ids,
                'execution_update':    w.id in recent_exec_ids,
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
        if not request.user.is_authenticated:
            return Response({'error': 'Login required.'}, status=status.HTTP_401_UNAUTHORIZED)
        period = request.query_params.get('period', 'monthly')
        loa_ids_param = request.query_params.get('loa_ids')
        loa_id = request.query_params.get('loa_id')

        cfg = self.PERIOD_CONFIG.get(period, self.PERIOD_CONFIG['monthly'])

        if loa_ids_param:
            ids = [int(x) for x in loa_ids_param.split(',') if x.strip().isdigit()]
            item_qs = WorkItem.objects.filter(work_id__in=ids)
        elif loa_id:
            item_qs = WorkItem.objects.filter(work_id=loa_id)
        else:
            item_qs = WorkItem.objects.all()

        sch_a_qty = item_qs.filter(schedule__istartswith='A').aggregate(t=Sum('qty'))['t'] or 0
        sch_b_qty = item_qs.filter(schedule__istartswith='B').aggregate(t=Sum('qty'))['t'] or 0

        cutoff = timezone.now() - timedelta(days=cfg['cutoff_days']) if cfg['cutoff_days'] else None

        supply_qs = WorkItemEntry.objects.filter(
            work_item__schedule__istartswith='A', entry_type='supply'
        )
        exec_qs = WorkItemEntry.objects.filter(
            work_item__schedule__istartswith='B', entry_type='execution'
        )
        if loa_ids_param and ids:
            supply_qs = supply_qs.filter(work_item__work_id__in=ids)
            exec_qs   = exec_qs.filter(work_item__work_id__in=ids)
        elif loa_id:
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

        # Financial: BillItem grouped by bill_date
        total_work_amount = item_qs.aggregate(t=Sum('total_amount'))['t'] or 0
        fin_totals = {}
        fin_qs = BillItem.objects.filter(bill_record__bill_date__isnull=False)
        if loa_ids_param and ids:
            fin_qs = fin_qs.filter(bill_record__work_id__in=ids)
        elif loa_id:
            fin_qs = fin_qs.filter(bill_record__work_id=loa_id)
        if cutoff:
            fin_qs = fin_qs.filter(bill_record__bill_date__gte=cutoff.date())
        for row in (fin_qs
                    .annotate(bucket=cfg['trunc']('bill_record__bill_date'))
                    .values('bucket').annotate(total=Sum('amt_total'))):
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
