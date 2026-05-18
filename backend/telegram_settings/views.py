import requests
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from users.views import _is_admin
from .models import TelegramBotConfig


def _get_config():
    obj, _ = TelegramBotConfig.objects.get_or_create(pk=1)
    return obj


@method_decorator(csrf_exempt, name='dispatch')
class TelegramConfigView(APIView):
    def get(self, request):
        if not _is_admin(request.user):
            return Response({'error': 'Forbidden.'}, status=status.HTTP_403_FORBIDDEN)
        cfg = _get_config()
        return Response({
            'bot_token':            cfg.bot_token,
            'upload_group_chat_id': cfg.upload_group_chat_id,
            'is_active':            cfg.is_active,
            'updated_at':           cfg.updated_at.strftime('%Y-%m-%d %H:%M') if cfg.updated_at else None,
        })

    def patch(self, request):
        if not _is_admin(request.user):
            return Response({'error': 'Forbidden.'}, status=status.HTTP_403_FORBIDDEN)
        cfg = _get_config()
        data = request.data
        if 'bot_token'            in data: cfg.bot_token            = data['bot_token'].strip()
        if 'upload_group_chat_id' in data: cfg.upload_group_chat_id = data['upload_group_chat_id'].strip()
        if 'is_active'            in data: cfg.is_active            = bool(data['is_active'])
        cfg.save()
        return Response({'message': 'Telegram settings saved.'})


@method_decorator(csrf_exempt, name='dispatch')
class TelegramTestView(APIView):
    """Send a test message to the upload group to verify bot token and chat ID."""
    def post(self, request):
        if not _is_admin(request.user):
            return Response({'error': 'Forbidden.'}, status=status.HTTP_403_FORBIDDEN)
        cfg = _get_config()
        if not cfg.bot_token:
            return Response({'error': 'Bot token not configured.'}, status=status.HTTP_400_BAD_REQUEST)
        if not cfg.upload_group_chat_id:
            return Response({'error': 'Upload group chat ID not configured.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            url = f'https://api.telegram.org/bot{cfg.bot_token}/sendMessage'
            resp = requests.post(url, json={
                'chat_id': cfg.upload_group_chat_id,
                'text': 'ManageWorks — Telegram bot connected successfully.',
            }, timeout=10)
            if resp.status_code == 200:
                return Response({'message': 'Test message sent to upload group.'})
            return Response({'error': resp.json().get('description', 'Telegram API error.')},
                            status=status.HTTP_502_BAD_GATEWAY)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_502_BAD_GATEWAY)
