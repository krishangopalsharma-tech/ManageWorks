from django.urls import path
from .views import WorkListView, LocationProgressView

urlpatterns = [
    path('works/',    WorkListView.as_view(),        name='location_progress_works'),
    path('data/',     LocationProgressView.as_view(), name='location_progress_data'),
]
