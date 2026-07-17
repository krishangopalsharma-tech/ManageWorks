from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from works.models import Work
from works.utils import is_admin_user as _is_admin
from .models import WorkDeleteLog


class WorkDeleteView(APIView):
    """DELETE /api/delete-log/works/<pk>/  — admin only, requires reason in body."""

    def delete(self, request, pk):
        if not _is_admin(request.user):
            return Response(
                {'error': 'Only admins can delete LOAs.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        reason = (request.data.get('reason') or '').strip()
        if not reason:
            return Response(
                {'error': 'A deletion reason is required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            work = Work.objects.get(pk=pk)
        except Work.DoesNotExist:
            return Response({'error': 'Work not found.'}, status=status.HTTP_404_NOT_FOUND)

        WorkDeleteLog.objects.create(
            work_id         = work.pk,
            loa_number      = work.loa_number or '',
            name_of_work    = work.name_of_work or '',
            contractor_name = work.contractor_name or '',
            deleted_by      = request.user,
            deleted_by_name = (request.user.get_full_name() or '').strip() or request.user.username,
            reason          = reason,
        )
        work.delete()
        return Response({'message': 'Work deleted and logged.'})


class DeleteLogListView(APIView):
    """GET /api/delete-log/  — admin only."""

    def get(self, request):
        if not _is_admin(request.user):
            return Response({'error': 'Forbidden.'}, status=status.HTTP_403_FORBIDDEN)

        logs = WorkDeleteLog.objects.all()
        data = [
            {
                'id':              log.id,
                'work_id':         log.work_id,
                'loa_number':      log.loa_number,
                'name_of_work':    log.name_of_work,
                'contractor_name': log.contractor_name,
                'deleted_by':      log.deleted_by_name,
                'reason':          log.reason,
                'deleted_at':      log.deleted_at,
            }
            for log in logs
        ]
        return Response(data)
