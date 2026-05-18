from django.urls import path
from .views import TelegramConfigView, TelegramTestView

urlpatterns = [
    path('', TelegramConfigView.as_view(), name='telegram_config'),
    path('test/', TelegramTestView.as_view(), name='telegram_test'),
]
