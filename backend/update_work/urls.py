from django.urls import path
from .views import (
    WorkUpdateDeleteView,
    UpdateWorkSearchView, UpdateWorkRetrieveView,
)

urlpatterns = [
    path('works/search/',          UpdateWorkSearchView.as_view(),   name='update_work_search'),
    path('works/<int:pk>/',        WorkUpdateDeleteView.as_view(),   name='work_update_delete'),
    path('works/<int:pk>/detail/', UpdateWorkRetrieveView.as_view(), name='update_work_detail'),
]
