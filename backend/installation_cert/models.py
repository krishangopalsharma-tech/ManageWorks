from django.db import models
from django.contrib.auth import get_user_model

from works.models import Work

User = get_user_model()


class GeneratedCertificate(models.Model):
    user         = models.ForeignKey(User, on_delete=models.CASCADE, related_name='generated_certs')
    work         = models.ForeignKey(Work, on_delete=models.CASCADE, related_name='generated_certs')
    cert_number  = models.CharField(max_length=200)
    entry_ids    = models.JSONField()
    designation  = models.CharField(max_length=200, blank=True)
    generated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-generated_at']

    def __str__(self):
        return f"{self.cert_number} ({self.work.loa_number})"
