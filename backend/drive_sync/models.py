import re
from django.db import models
from django.contrib.auth.models import User

_FOLDER_ID_RE = re.compile(r'/folders/([a-zA-Z0-9_-]+)')


def extract_folder_id(url_or_id):
    """Pull the folder ID out of a pasted Drive folder URL, or pass through
    if it's already a bare ID (no slashes)."""
    url_or_id = (url_or_id or '').strip()
    if not url_or_id:
        return ''
    match = _FOLDER_ID_RE.search(url_or_id)
    if match:
        return match.group(1)
    return url_or_id.rstrip('/').split('/')[-1].split('?')[0]


class DriveSyncSettings(models.Model):
    """Single-row config — the Drive API key. Never hardcoded/env-baked so a
    different deployment (different division, different Google account) can
    swap it from the settings UI without a code change."""
    api_key    = models.CharField(max_length=200, blank=True, default='')
    is_active  = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = 'Drive Sync Settings'
        verbose_name_plural = 'Drive Sync Settings'

    def __str__(self):
        return 'Drive Sync Settings'


class DriveFolderLink(models.Model):
    """A consignee's own Drive folders — self-service, one row per user."""
    user                = models.OneToOneField(User, on_delete=models.CASCADE, related_name='drive_folder_link')
    workbills_folder_url = models.URLField(max_length=500, blank=True, default='')
    workbills_folder_id  = models.CharField(max_length=200, blank=True, editable=False)
    crn_folder_url        = models.URLField(max_length=500, blank=True, default='')
    crn_folder_id          = models.CharField(max_length=200, blank=True, editable=False)
    connected_at        = models.DateTimeField(auto_now_add=True)
    last_synced_at      = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name        = 'Drive Folder Link'
        verbose_name_plural = 'Drive Folder Links'

    def save(self, *args, **kwargs):
        self.workbills_folder_id = extract_folder_id(self.workbills_folder_url)
        self.crn_folder_id       = extract_folder_id(self.crn_folder_url)
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.user.username} drive link'


class SyncedFile(models.Model):
    """Dedup/audit log — one row per Drive file we've ever seen. The sole
    source of truth for 'already processed' so a sync never re-downloads or
    re-parses an unchanged file."""
    KIND_CHOICES = (
        ('bill',    'Bill'),
        ('receipt', 'Receipt (CRN)'),
    )
    STATUS_CHOICES = (
        ('synced',       'Synced'),
        ('needs_review', 'Needs Review'),
        ('error',        'Error'),
    )

    folder_link   = models.ForeignKey(DriveFolderLink, on_delete=models.CASCADE, related_name='synced_files')
    drive_file_id = models.CharField(max_length=200)
    filename      = models.CharField(max_length=500, blank=True, default='')
    modified_time = models.CharField(max_length=100, blank=True, default='')  # Drive's ISO timestamp, stored raw
    kind          = models.CharField(max_length=20, choices=KIND_CHOICES)
    status        = models.CharField(max_length=20, choices=STATUS_CHOICES)
    reason        = models.TextField(blank=True, default='')
    matched_work  = models.ForeignKey('works.Work', null=True, blank=True, on_delete=models.SET_NULL)
    synced_at     = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [('folder_link', 'drive_file_id')]
        ordering = ['-synced_at']
        verbose_name        = 'Synced File'
        verbose_name_plural = 'Synced Files'

    def __str__(self):
        return f'{self.filename} ({self.status})'
