from django.urls import path
from .views import (
    WorkSearchView, WorkItemSearchView,
    MBRecordListCreateView, MBRecordDetailView,
    MBSummaryView, PDFImportView,
)

urlpatterns = [
    path('works/',                     WorkSearchView.as_view(),         name='mb_work_search'),
    path('works/<int:work_id>/items/', WorkItemSearchView.as_view(),     name='mb_work_items'),
    path('records/',                   MBRecordListCreateView.as_view(), name='mb_records'),
    path('records/<int:pk>/',          MBRecordDetailView.as_view(),     name='mb_record_detail'),
    path('summary/',                   MBSummaryView.as_view(),          name='mb_summary'),
    path('import-pdf/',                PDFImportView.as_view(),          name='mb_import_pdf'),
]
