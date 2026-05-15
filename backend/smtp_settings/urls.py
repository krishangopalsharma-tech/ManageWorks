from django.urls import path
from .views import SmtpConfigView, SmtpTestView

urlpatterns = [
    path('', SmtpConfigView.as_view(), name='smtp_config'),
    path('test/', SmtpTestView.as_view(), name='smtp_test'),
]
