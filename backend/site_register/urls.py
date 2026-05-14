from django.urls import path
from .views import SiteRegisterView

urlpatterns = [
    path('', SiteRegisterView.as_view(), name='site_register'),
]
