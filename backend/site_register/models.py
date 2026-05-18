import secrets
from django.db import models
from django.contrib.auth.models import User
from works.models import Work, WorkItem


class TelegramUserLink(models.Model):
    """Maps a ManageWorks user to their Telegram account."""
    user             = models.OneToOneField(User, on_delete=models.CASCADE, related_name='telegram_link')
    telegram_user_id = models.BigIntegerField(unique=True)
    telegram_chat_id = models.BigIntegerField()
    is_verified      = models.BooleanField(default=False)
    linked_at        = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} → tg:{self.telegram_user_id}"


class TelegramLinkOTP(models.Model):
    """One-time code shown in web app; contractor/SSE sends it to bot to link account."""
    user       = models.OneToOneField(User, on_delete=models.CASCADE, related_name='telegram_otp')
    code       = models.CharField(max_length=20, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    used       = models.BooleanField(default=False)

    @staticmethod
    def generate_for(user):
        TelegramLinkOTP.objects.filter(user=user).delete()
        code = 'TG-' + secrets.token_hex(4).upper()
        return TelegramLinkOTP.objects.create(user=user, code=code)

    def __str__(self):
        return f"{self.user.username}: {self.code}"


class WorkContractorTelegram(models.Model):
    """Maps a Work/LOA to one or more Telegram-linked users (sse or contractor)."""
    ROLE_CHOICES = [('sse', 'SSE'), ('contractor', 'Contractor')]

    work          = models.ForeignKey(Work, on_delete=models.CASCADE, related_name='telegram_parties')
    telegram_link = models.ForeignKey(TelegramUserLink, on_delete=models.CASCADE, related_name='work_mappings')
    role          = models.CharField(max_length=20, choices=ROLE_CHOICES)
    is_active     = models.BooleanField(default=True)
    linked_at     = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('work', 'telegram_link')

    def __str__(self):
        return f"{self.work.loa_number} ↔ {self.telegram_link.user.username} ({self.role})"


class SiteRegisterThread(models.Model):
    """A single site register entry — either SSE-initiated or contractor-initiated."""
    CATEGORY_CHOICES = [
        ('order',                'SSE Order'),
        ('progress',             'Progress Update'),
        ('hindrance',            'Hindrance'),
        ('inspection_request',   'Inspection Request'),
        ('document_submission',  'Document Submission'),
        ('general_remark',       'General Remark'),
    ]
    STATUS_CHOICES = [
        ('open',     'Open'),
        ('replied',  'Replied'),
        ('verified', 'Verified'),
        ('closed',   'Closed'),
    ]
    ROLE_CHOICES = [('sse', 'SSE'), ('contractor', 'Contractor')]

    work              = models.ForeignKey(Work, on_delete=models.CASCADE, related_name='sr_threads')
    work_item         = models.ForeignKey(WorkItem, null=True, blank=True, on_delete=models.SET_NULL, related_name='sr_threads')
    initiated_by_role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    category          = models.CharField(max_length=30, choices=CATEGORY_CHOICES)
    initial_text      = models.TextField()
    status            = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open')
    created_by        = models.ForeignKey(User, null=True, on_delete=models.SET_NULL, related_name='sr_threads_created')
    tg_order_message_id = models.BigIntegerField(null=True, blank=True)
    created_at        = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"SR-{self.pk:06d} [{self.work.loa_number}] {self.category}"


class SiteRegisterMessage(models.Model):
    """A reply or follow-up message within a SiteRegisterThread."""
    ROLE_CHOICES = [('sse', 'SSE'), ('contractor', 'Contractor')]

    thread      = models.ForeignKey(SiteRegisterThread, on_delete=models.CASCADE, related_name='messages')
    sender      = models.ForeignKey(User, null=True, on_delete=models.SET_NULL, related_name='sr_messages')
    sender_role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    message_text = models.TextField(blank=True)
    tg_message_id = models.BigIntegerField(null=True, blank=True)
    created_at  = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Msg in SR-{self.thread_id:06d} by {self.sender_role}"


class SiteRegisterAttachment(models.Model):
    """
    Pointer to a file uploaded via Telegram.
    Binary stays in Telegram; we store only file_id and archive group message_id.
    """
    FILE_TYPE_CHOICES = [
        ('photo',    'Photo'),
        ('document', 'Document'),
        ('pdf',      'PDF'),
    ]

    message               = models.ForeignKey(SiteRegisterMessage, on_delete=models.CASCADE, related_name='attachments')
    tg_file_id            = models.TextField()
    tg_file_unique_id     = models.TextField(blank=True)
    original_filename     = models.CharField(max_length=500, blank=True)
    file_type             = models.CharField(max_length=20, choices=FILE_TYPE_CHOICES)
    archive_group_message_id = models.BigIntegerField(null=True, blank=True)
    uploaded_at           = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.file_type} for SR-{self.message.thread_id:06d}"


class BotSession(models.Model):
    """Per-chat state for the Telegram bot conversation flow."""
    telegram_chat_id = models.BigIntegerField(unique=True)
    state            = models.CharField(max_length=100, default='idle')
    context          = models.JSONField(default=dict, blank=True)
    updated_at       = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"BotSession({self.telegram_chat_id}, {self.state})"
