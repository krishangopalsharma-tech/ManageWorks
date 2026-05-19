import random
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta
from works.models import Work, WorkItem


class TelegramUserLink(models.Model):
    """Maps a ManageWorks user to their Telegram account."""
    user             = models.OneToOneField(User, on_delete=models.CASCADE, related_name='telegram_link')
    telegram_user_id = models.BigIntegerField(unique=True)
    telegram_chat_id = models.BigIntegerField()
    is_verified      = models.BooleanField(default=False)
    linked_at        = models.DateTimeField(auto_now_add=True)
    # Onboarding fields (filled by bot during registration)
    onboard_name        = models.CharField(max_length=200, blank=True)
    onboard_designation = models.CharField(max_length=200, blank=True)
    onboard_mobile      = models.CharField(max_length=20, blank=True)

    def __str__(self):
        return f"{self.user.username} → tg:{self.telegram_user_id}"


class TelegramLinkOTP(models.Model):
    """6-digit numeric code shown in web app; user types it in bot to link account."""
    user       = models.OneToOneField(User, on_delete=models.CASCADE, related_name='telegram_otp')
    code       = models.CharField(max_length=6, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True)
    used       = models.BooleanField(default=False)

    @staticmethod
    def generate_for(user):
        TelegramLinkOTP.objects.filter(user=user).delete()
        # 6-digit numeric, guaranteed unique
        while True:
            code = f"{random.randint(0, 999999):06d}"
            if not TelegramLinkOTP.objects.filter(code=code).exists():
                break
        expires = timezone.now() + timedelta(minutes=1)
        return TelegramLinkOTP.objects.create(user=user, code=code, expires_at=expires)

    @property
    def is_expired(self):
        return timezone.now() > self.expires_at

    def __str__(self):
        return f"{self.user.username}: {self.code}"


class WorkContractorTelegram(models.Model):
    """Maps a Work/LOA to site supervisors. Rly Officials need no mapping."""
    ROLE_CHOICES = [('site_supervisor', 'Site Supervisor')]

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
        ('order',                'Rly Official Order'),
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
    ROLE_CHOICES = [('rly_official', 'Rly Official'), ('site_supervisor', 'Site Supervisor')]

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
    ROLE_CHOICES = [('rly_official', 'Rly Official'), ('site_supervisor', 'Site Supervisor')]

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


class SupervisorInvite(models.Model):
    """One-time code generated by admin; supervisor types it in bot to get linked + mapped to LOAs."""
    code         = models.CharField(max_length=6, unique=True)
    loa_ids      = models.JSONField(default=list)
    created_by   = models.ForeignKey(User, on_delete=models.CASCADE, related_name='supervisor_invites')
    created_at   = models.DateTimeField(auto_now_add=True)
    expires_at   = models.DateTimeField()
    used         = models.BooleanField(default=False)
    used_by_link = models.ForeignKey(
        'TelegramUserLink', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='invite_used'
    )

    @staticmethod
    def generate(loa_ids, created_by):
        SupervisorInvite.objects.filter(created_by=created_by, used=False).delete()
        while True:
            code = f"{random.randint(0, 999999):06d}"
            if (not SupervisorInvite.objects.filter(code=code).exists() and
                    not TelegramLinkOTP.objects.filter(code=code).exists()):
                break
        expires = timezone.now() + timedelta(minutes=5)
        return SupervisorInvite.objects.create(
            code=code, loa_ids=loa_ids, created_by=created_by, expires_at=expires
        )

    @property
    def is_expired(self):
        return timezone.now() > self.expires_at

    def __str__(self):
        return f"Invite {self.code} by {self.created_by.username}"


class RlyTelegramLink(models.Model):
    """
    Delegate railway officials added by a system user (SSE/admin) via RlyOfficialInvite.
    The linked person may or may not have a ManageWorks account.
    If HRMS found: system_user points to existing User.
    If HRMS not found: ghost_user is created (username=rly_{tg_user_id}).
    Use .effective_user property to get the Django User to pass to FKs.
    """
    added_by         = models.ForeignKey(User, on_delete=models.CASCADE, related_name='rly_delegate_links')
    system_user      = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='rly_telegram_link_system')
    ghost_user       = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='rly_telegram_link_ghost')
    hrms_id          = models.CharField(max_length=100, blank=True)
    telegram_user_id = models.BigIntegerField(unique=True)
    telegram_chat_id = models.BigIntegerField()
    name             = models.CharField(max_length=200, blank=True)
    designation      = models.CharField(max_length=200, blank=True)
    mobile           = models.CharField(max_length=20, blank=True)
    is_verified      = models.BooleanField(default=False)
    linked_at        = models.DateTimeField(auto_now_add=True)

    @property
    def effective_user(self):
        return self.system_user or self.ghost_user

    @property
    def display_name(self):
        if self.system_user:
            return self.system_user.first_name or self.system_user.username
        return self.name or self.hrms_id or f"tg:{self.telegram_user_id}"

    def __str__(self):
        return f"RlyDelegate {self.hrms_id} → tg:{self.telegram_user_id} (added by {self.added_by.username})"


class RlyOfficialInvite(models.Model):
    """One-time code generated by a rly official; another rly official types it in bot to link."""
    code           = models.CharField(max_length=6, unique=True)
    created_by     = models.ForeignKey(User, on_delete=models.CASCADE, related_name='rly_official_invites')
    created_at     = models.DateTimeField(auto_now_add=True)
    expires_at     = models.DateTimeField()
    used           = models.BooleanField(default=False)
    used_by_link   = models.ForeignKey('RlyTelegramLink', null=True, blank=True, on_delete=models.SET_NULL)

    @staticmethod
    def generate(created_by):
        RlyOfficialInvite.objects.filter(created_by=created_by, used=False).delete()
        while True:
            code = f"{random.randint(0, 999999):06d}"
            if (not RlyOfficialInvite.objects.filter(code=code).exists() and
                    not TelegramLinkOTP.objects.filter(code=code).exists() and
                    not SupervisorInvite.objects.filter(code=code).exists()):
                break
        expires = timezone.now() + timedelta(minutes=5)
        return RlyOfficialInvite.objects.create(code=code, created_by=created_by, expires_at=expires)

    @property
    def is_expired(self):
        return timezone.now() > self.expires_at

    def __str__(self):
        return f"RlyInvite {self.code} by {self.created_by.username}"


class BotSession(models.Model):
    """Per-chat state for the Telegram bot conversation flow."""
    telegram_chat_id = models.BigIntegerField(unique=True)
    state            = models.CharField(max_length=100, default='idle')
    context          = models.JSONField(default=dict, blank=True)
    updated_at       = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"BotSession({self.telegram_chat_id}, {self.state})"
