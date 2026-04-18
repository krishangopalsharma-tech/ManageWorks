from django.urls import path
from .views import WorkListView, ItemSearchView

urlpatterns = [
    path('works/',  WorkListView.as_view(),  name='item_progress_works'),
    path('search/', ItemSearchView.as_view(), name='item_search'),
]
