from django.urls import path
from .views import MyProfileView, ChangePasswordView

urlpatterns = [
    path('', MyProfileView.as_view(), name='my_profile'),
    path('password/', ChangePasswordView.as_view(), name='change_password'),
]
