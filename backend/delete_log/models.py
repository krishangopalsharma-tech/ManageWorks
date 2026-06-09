from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class WorkDeleteLog(models.Model):
    work_id          = models.IntegerField()
    loa_number       = models.CharField(max_length=200, blank=True)
    name_of_work     = models.TextField(blank=True)
    contractor_name  = models.CharField(max_length=200, blank=True)
    deleted_by       = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='work_deletions')
    deleted_by_name  = models.CharField(max_length=200, blank=True)
    reason           = models.TextField()
    deleted_at       = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-deleted_at']
