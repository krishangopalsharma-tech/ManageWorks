from django.urls import path
from .views import UserListView, UserCreateView, MeView

urlpatterns = [
    path('me/',     MeView.as_view(),        name='user_me'),
    path('',        UserListView.as_view(),   name='user_list'),
    path('create/', UserCreateView.as_view(), name='user_create'),
]
