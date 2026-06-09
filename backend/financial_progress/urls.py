from django.urls import path
from .views import ParseBillPDFView, BillListCreateView, BillDeleteView, FinancialSummaryView

urlpatterns = [
    path('parse/',           ParseBillPDFView.as_view(),   name='fp_parse'),
    path('bills/',           BillListCreateView.as_view(), name='fp_bills'),
    path('bills/<int:pk>/',  BillDeleteView.as_view(),     name='fp_bill_delete'),
    path('summary/',         FinancialSummaryView.as_view(), name='fp_summary'),
]
