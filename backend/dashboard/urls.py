from django.urls import path
from .views import DashboardStatsView, ProgressTrendView

urlpatterns = [
    path('', DashboardStatsView.as_view(), name='dashboard_stats'),
    path('trend/', ProgressTrendView.as_view(), name='dashboard_trend'),
]
