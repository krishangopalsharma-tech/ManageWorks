from django.urls import path
from .views import (
    SupplyWorkSearchView, SupplyWorkRetrieveView,
    SupplyEntryView, SupplyEntryUpdateView, ParseSupplyPDFsView,
)

urlpatterns = [
    path('works/search/',                SupplyWorkSearchView.as_view(),   name='supply_work_search'),
    path('works/<int:pk>/detail/',       SupplyWorkRetrieveView.as_view(), name='supply_work_detail'),
    path('items/<int:item_id>/entries/', SupplyEntryView.as_view(),        name='supply_item_entries'),
    path('entries/<int:entry_id>/',      SupplyEntryUpdateView.as_view(),  name='supply_entry_update'),
    path('parse-pdfs/',                  ParseSupplyPDFsView.as_view(),    name='supply_parse_pdfs'),
]
