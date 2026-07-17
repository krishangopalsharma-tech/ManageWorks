from django.urls import path
from .views import (
    ExecutionWorkSearchView, ExecutionWorkRetrieveView,
    ExecutionEntryView, ExecutionEntryUpdateView,
)

urlpatterns = [
    path('works/search/',                ExecutionWorkSearchView.as_view(),   name='execution_work_search'),
    path('works/<int:pk>/detail/',       ExecutionWorkRetrieveView.as_view(), name='execution_work_detail'),
    path('items/<int:item_id>/entries/', ExecutionEntryView.as_view(),        name='execution_item_entries'),
    path('entries/<int:entry_id>/',      ExecutionEntryUpdateView.as_view(),  name='execution_entry_update'),
]
