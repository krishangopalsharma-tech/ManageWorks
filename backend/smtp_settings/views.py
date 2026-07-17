from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.core.mail import EmailMessage
from django.core.mail.backends.smtp import EmailBackend

from .models import SmtpConfig
from users.views import _is_super_admin


def _get_config():
    obj, _ = SmtpConfig.objects.get_or_create(pk=1)
    return obj


@method_decorator(csrf_exempt, name='dispatch')
class SmtpTestView(APIView):
    def post(self, request):
        if not _is_super_admin(request.user):
            return Response({'error': 'Forbidden.'}, status=status.HTTP_403_FORBIDDEN)
        to_email = (request.data.get('to_email') or '').strip()
        if not to_email:
            return Response({'error': 'to_email is required.'}, status=status.HTTP_400_BAD_REQUEST)
        cfg = _get_config()
        if not cfg.host_user or not cfg.host_password:
            return Response({'error': 'SMTP credentials not configured.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            backend = EmailBackend(
                host=cfg.host, port=cfg.port,
                username=cfg.host_user, password=cfg.host_password,
                use_tls=cfg.use_tls, fail_silently=False,
                timeout=10,
            )
            msg = EmailMessage(
                subject='ManageWorks — SMTP Test',
                body='This is a test email from ManageWorks. Your SMTP configuration is working correctly.',
                from_email=cfg.from_email or cfg.host_user,
                to=[to_email],
                connection=backend,
            )
            msg.send()
            return Response({'message': f'Test email sent to {to_email}.'})
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_502_BAD_GATEWAY)


@method_decorator(csrf_exempt, name='dispatch')
class SmtpConfigView(APIView):
    def get(self, request):
        if not _is_super_admin(request.user):
            return Response({'error': 'Forbidden.'}, status=status.HTTP_403_FORBIDDEN)
        cfg = _get_config()
        return Response({
            'host':          cfg.host,
            'port':          cfg.port,
            'use_tls':       cfg.use_tls,
            'host_user':     cfg.host_user,
            'host_password': cfg.host_password,
            'from_email':    cfg.from_email,
            'updated_at':    cfg.updated_at.strftime('%Y-%m-%d %H:%M') if cfg.updated_at else None,
        })

    def patch(self, request):
        if not _is_super_admin(request.user):
            return Response({'error': 'Forbidden.'}, status=status.HTTP_403_FORBIDDEN)
        cfg = _get_config()
        data = request.data
        if 'host'          in data: cfg.host          = data['host'].strip()
        if 'port'          in data: cfg.port          = int(data['port'])
        if 'use_tls'       in data: cfg.use_tls       = bool(data['use_tls'])
        if 'host_user'     in data: cfg.host_user     = data['host_user'].strip()
        if 'host_password' in data: cfg.host_password = data['host_password']
        if 'from_email'    in data: cfg.from_email    = data['from_email'].strip()
        cfg.save()
        return Response({'message': 'SMTP settings saved.'})
