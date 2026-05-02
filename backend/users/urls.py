from django.urls import path
from .views import (
    RegisterView, LoginView, LogoutView, MeView,
    PendingUsersView, ApproveUserView, RejectUserView, AllUsersView,
)

urlpatterns = [
    path('register/',          RegisterView.as_view(),              name='auth_register'),
    path('login/',             LoginView.as_view(),                 name='auth_login'),
    path('logout/',            LogoutView.as_view(),                name='auth_logout'),
    path('me/',                MeView.as_view(),                    name='auth_me'),
    path('pending/',           PendingUsersView.as_view(),          name='auth_pending'),
    path('approve/<int:user_id>/', ApproveUserView.as_view(),       name='auth_approve'),
    path('reject/<int:user_id>/',  RejectUserView.as_view(),        name='auth_reject'),
    path('all/',               AllUsersView.as_view(),              name='auth_all'),
]
