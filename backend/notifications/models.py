from django.db import models
from django.contrib.auth.models import User
from site_register.models import SiteRegisterThread


class Notification(models.Model):
    TYPE_CHOICES = [
        ('new_sr',         'Site Register'),
        ('ss_entry',       'Supply'),
        ('si_entry',       'Supply and Installation'),
        ('ee_entry',       'Execution'),
        ('financial',      'Financial'),
        ('loa_unassigned', 'LOA Unassigned'),
    ]
    user       = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    notif_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    title      = models.CharField(max_length=300)
    body       = models.TextField(blank=True)
    thread     = models.ForeignKey(SiteRegisterThread, null=True, blank=True, on_delete=models.SET_NULL, related_name='notifications')
    is_read    = models.BooleanField(default=False)
    read_at    = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Notif({self.notif_type}) → {self.user.username}"
