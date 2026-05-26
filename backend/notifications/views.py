from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from .models import Notification


def _serialize(n):
    thread = n.thread
    return {
        'id':         n.pk,
        'notif_type': n.notif_type,
        'title':      n.title,
        'body':       n.body,
        'is_read':    n.is_read,
        'created_at': n.created_at.isoformat(),
        'thread_id':  thread.pk if thread else None,
        'loa_number': thread.work.loa_number if thread else None,
        'sr_number':  thread.sr_number if thread else None,
    }


class NotificationListView(APIView):
    """
    GET  /api/notifications/  → {notifications, unread_count}
    POST /api/notifications/  → mark all read
    """
    def get(self, request):
        if not request.user.is_authenticated:
            return Response({'error': 'Login required.'}, status=status.HTTP_401_UNAUTHORIZED)
        qs = (
            Notification.objects
            .filter(user=request.user)
            .select_related('thread', 'thread__work')
            .order_by('-created_at')[:60]
        )
        unread_count = Notification.objects.filter(user=request.user, is_read=False).count()
        return Response({'notifications': [_serialize(n) for n in qs], 'unread_count': unread_count})

    def post(self, request):
        if not request.user.is_authenticated:
            return Response({'error': 'Login required.'}, status=status.HTTP_401_UNAUTHORIZED)
        Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
        return Response({'ok': True})


class NotificationDetailView(APIView):
    """POST /api/notifications/<notif_id>/read/ → mark one read"""
    def post(self, request, notif_id):
        if not request.user.is_authenticated:
            return Response({'error': 'Login required.'}, status=status.HTTP_401_UNAUTHORIZED)
        Notification.objects.filter(pk=notif_id, user=request.user).update(is_read=True)
        return Response({'ok': True})
