from django.core.mail import EmailMessage
from django.core.mail.backends.smtp import EmailBackend


def _get_smtp_config():
    from smtp_settings.models import SmtpConfig
    obj, _ = SmtpConfig.objects.get_or_create(pk=1)
    return obj


def send_password_email(to_email: str, user_name: str, hrms_id: str, plain_password: str) -> None:
    cfg = _get_smtp_config()
    backend = EmailBackend(
        host=cfg.host,
        port=cfg.port,
        username=cfg.host_user,
        password=cfg.host_password,
        use_tls=cfg.use_tls,
        fail_silently=False,
    )
    subject = 'ManageWorks — Your Password'
    body = (
        f'Hello {user_name},\n\n'
        f'Your ManageWorks login credentials:\n\n'
        f'  HRMS ID : {hrms_id}\n'
        f'  Password: {plain_password}\n\n'
        f'Please keep this information secure.\n\n'
        f'— ManageWorks Team'
    )
    msg = EmailMessage(
        subject=subject,
        body=body,
        from_email=cfg.from_email,
        to=[to_email],
        connection=backend,
    )
    msg.send()
