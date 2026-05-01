from django.urls import path
from .views import (
    WorkSearchView, WorkItemSearchView, ItemPriorInfoView,
    MBRecordListCreateView, MBRecordDetailView,
    MBSummaryView, PDFImportView,
)

urlpatterns = [
    path('works/',                         WorkSearchView.as_view(),         name='mb_work_search'),
    path('works/<int:work_id>/items/',     WorkItemSearchView.as_view(),     name='mb_work_items'),
    path('items/<int:work_item_id>/prior/', ItemPriorInfoView.as_view(),     name='mb_item_prior'),
    path('records/',                       MBRecordListCreateView.as_view(), name='mb_records'),
    path('records/<int:pk>/',              MBRecordDetailView.as_view(),     name='mb_record_detail'),
    path('summary/',                       MBSummaryView.as_view(),          name='mb_summary'),
    path('import-pdf/',                    PDFImportView.as_view(),          name='mb_import_pdf'),
]
