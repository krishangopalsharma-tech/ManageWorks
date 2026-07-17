from django.urls import path
from .views import (
    WorkItemEntryView, WorkUpdateDeleteView, WorkItemEntryUpdateView, ParsePDFsView,
    UpdateWorkSearchView, UpdateWorkRetrieveView,
)

urlpatterns = [
    path('works/search/',                    UpdateWorkSearchView.as_view(),   name='update_work_search'),
    path('works/<int:pk>/',                  WorkUpdateDeleteView.as_view(),  name='work_update_delete'),
    path('works/<int:pk>/detail/',           UpdateWorkRetrieveView.as_view(), name='update_work_detail'),
    path('items/<int:item_id>/entries/',     WorkItemEntryView.as_view(),     name='work_item_entries'),
    path('entries/<int:entry_id>/',          WorkItemEntryUpdateView.as_view(), name='entry_update'),
    path('parse-pdfs/',                      ParsePDFsView.as_view(),          name='parse_pdfs'),
]
