from django.urls import path
from .views import NotificationListView, NotificationDetailView

urlpatterns = [
    path('',                     NotificationListView.as_view(),   name='notifications'),
    path('<int:notif_id>/read/', NotificationDetailView.as_view(), name='notification_read'),
]
