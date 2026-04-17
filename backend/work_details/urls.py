from django.urls import path
from .views import WorkSearchView

urlpatterns = [
    path('search/', WorkSearchView.as_view(), name='work_search'),
]
