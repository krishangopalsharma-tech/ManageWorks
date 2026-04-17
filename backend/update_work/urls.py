from django.urls import path
from .views import WorkItemEntryView, WorkUpdateDeleteView

urlpatterns = [
    # Work-level edit / delete
    path('works/<int:pk>/', WorkUpdateDeleteView.as_view(), name='work_update_delete'),

    # Lot-entry submission per item
    path('items/<int:item_id>/entries/', WorkItemEntryView.as_view(), name='work_item_entries'),
]
