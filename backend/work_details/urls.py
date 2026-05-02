from django.urls import path
from .views import WorkSearchView, WorkRetrieveView

urlpatterns = [
    path('search/',      WorkSearchView.as_view(),   name='work_search'),
    path('<int:pk>/',    WorkRetrieveView.as_view(),  name='work_detail'),
]
