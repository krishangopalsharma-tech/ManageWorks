from django.db import models
from django.contrib.auth.models import User


class UserProfile(models.Model):
    ROLE_CHOICES = [
        ('consignee', 'Consignee'),
        ('admin', 'Admin'),
        ('sse', 'SSE'),
        ('contractor', 'Contractor'),
    ]

    user           = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    designation    = models.CharField(max_length=150)
    pf_number      = models.CharField(max_length=50)
    is_approved    = models.BooleanField(default=False)
    role           = models.CharField(max_length=20, choices=ROLE_CHOICES, default='consignee')
    created_at     = models.DateTimeField(auto_now_add=True)
    plain_password = models.CharField(max_length=128, blank=True, default='')

    def __str__(self):
        return f"{self.user.first_name} ({self.user.username})"
