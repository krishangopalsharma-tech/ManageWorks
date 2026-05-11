from django.urls import path
from .views import (
    LOAListView, LOAItemsView, EntriesPreviewView,
    SuggestCertNumberView, PreviewCertView, GenerateCertView,
    CertificateListView, CertificateDetailView, CertificatePDFView,
)

urlpatterns = [
    path('loas/',                      LOAListView.as_view(),          name='ic_loa_list'),
    path('items/',                     LOAItemsView.as_view(),          name='ic_items'),
    path('entries/',                   EntriesPreviewView.as_view(),    name='ic_entries'),
    path('suggest-number/',            SuggestCertNumberView.as_view(), name='ic_suggest_number'),
    path('preview/',                   PreviewCertView.as_view(),       name='ic_preview'),
    path('generate/',                  GenerateCertView.as_view(),      name='ic_generate'),
    path('certificates/',              CertificateListView.as_view(),   name='ic_cert_list'),
    path('certificates/<int:pk>/',     CertificateDetailView.as_view(), name='ic_cert_detail'),
    path('certificates/<int:pk>/pdf/', CertificatePDFView.as_view(),    name='ic_cert_pdf'),
]
