from django.urls import path
from .views import WorkItemEntryView, WorkUpdateDeleteView, WorkItemEntryUpdateView

urlpatterns = [
    path('works/<int:pk>/',                  WorkUpdateDeleteView.as_view(),  name='work_update_delete'),
    path('items/<int:item_id>/entries/',     WorkItemEntryView.as_view(),     name='work_item_entries'),
    path('entries/<int:entry_id>/',          WorkItemEntryUpdateView.as_view(), name='entry_update'),
]
