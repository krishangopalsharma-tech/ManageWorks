from django.db import models
import re


class SiteGSheet(models.Model):
    name       = models.CharField(max_length=200)
    sheet_url  = models.URLField(max_length=500)
    sheet_id   = models.CharField(max_length=200, blank=True, editable=False)
    is_active  = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        verbose_name        = 'Site GSheet'
        verbose_name_plural = 'Site GSheets'

    def save(self, *args, **kwargs):
        match = re.search(r'/spreadsheets/d/([a-zA-Z0-9-_]+)', self.sheet_url)
        if match:
            self.sheet_id = match.group(1)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name
