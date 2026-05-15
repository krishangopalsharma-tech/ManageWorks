from django.db import models


class SmtpConfig(models.Model):
    host          = models.CharField(max_length=255, default='smtp.gmail.com')
    port          = models.PositiveIntegerField(default=587)
    use_tls       = models.BooleanField(default=True)
    host_user     = models.EmailField(max_length=255, default='adimanageworks@gmail.com')
    host_password = models.CharField(max_length=255, blank=True, default='')
    from_email    = models.EmailField(max_length=255, default='adimanageworks@gmail.com')
    updated_at    = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'SMTP Configuration'

    def __str__(self):
        return f'SMTP: {self.host_user}@{self.host}'
