from django.urls import path
from .views import StatusView, ConnectView, RunSyncView, AdminOverviewView, AdminConfigView

urlpatterns = [
    path('status/',          StatusView.as_view(),         name='drive_sync_status'),
    path('connect/',         ConnectView.as_view(),        name='drive_sync_connect'),
    path('run/',             RunSyncView.as_view(),        name='drive_sync_run'),
    path('admin/overview/',  AdminOverviewView.as_view(),  name='drive_sync_admin_overview'),
    path('admin/config/',    AdminConfigView.as_view(),    name='drive_sync_admin_config'),
]
