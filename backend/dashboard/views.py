from rest_framework.views import APIView
from rest_framework.response import Response
from works.models import Work, WorkItem


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
        total_supplied_value = 0
        total_scheduled_value = 0

        for item in items:
            q = item.qty or 0
            sq = item.supplied_quantity or 0

            item_prog = (sq / q) if q > 0 else 0

            sch = str(item.schedule).upper().strip() if item.schedule else ''
            if sch.startswith('A'):
                supply_progress_sum += item_prog
                supply_count += 1
            elif sch.startswith('B'):
                exec_progress_sum += item_prog
                exec_count += 1

            rate = item.unit_rate_rs or 0
            if q > 0 and rate > 0:
                total_scheduled_value += q * rate
                total_supplied_value += sq * rate

        supply_avg = (supply_progress_sum / supply_count * 100) if supply_count > 0 else 0
        exec_avg = (exec_progress_sum / exec_count * 100) if exec_count > 0 else 0
        overall_count = supply_count + exec_count
        overall_avg = ((supply_progress_sum + exec_progress_sum) / overall_count * 100) if overall_count > 0 else 0
        fin_prog = (total_supplied_value / total_scheduled_value * 100) if total_scheduled_value > 0 else 0

        loa_list = [
            {
                'id': w.id,
                'label': f"{w.tender_number or 'Unknown Tender'} | {w.loa_number or 'Unknown LOA'} | {w.contractor_name or 'Unknown'}"
            }
            for w in Work.objects.all()
        ]

        return Response({
            'supply': round(supply_avg, 2),
            'execution': round(exec_avg, 2),
            'overall': round(overall_avg, 2),
            'financial': round(fin_prog, 2),
            'loas': loa_list,
        })
