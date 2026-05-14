from django.urls import path
from .views import SiteGSheetListCreateView, SiteGSheetDetailView

urlpatterns = [
    path('sheets/',        SiteGSheetListCreateView.as_view(), name='site_gsheet_list'),
    path('sheets/<int:pk>/', SiteGSheetDetailView.as_view(),  name='site_gsheet_detail'),
]
