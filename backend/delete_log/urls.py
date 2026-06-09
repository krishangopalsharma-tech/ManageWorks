from django.urls import path
from .views import WorkDeleteView, DeleteLogListView

urlpatterns = [
    path('',               DeleteLogListView.as_view(), name='delete_log_list'),
    path('works/<int:pk>/', WorkDeleteView.as_view(),   name='work_delete_logged'),
]
