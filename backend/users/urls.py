from django.urls import path
from .views import (
    RegisterView, LoginView, LogoutView, MeView,
    PendingUsersView, ApproveUserView, RejectUserView, AllUsersView,
    UpdateRoleView, RevokeUserView,
)

urlpatterns = [
    path('register/',                  RegisterView.as_view(),     name='auth_register'),
    path('login/',                     LoginView.as_view(),        name='auth_login'),
    path('logout/',                    LogoutView.as_view(),       name='auth_logout'),
    path('me/',                        MeView.as_view(),           name='auth_me'),
    path('pending/',                   PendingUsersView.as_view(), name='auth_pending'),
    path('approve/<int:user_id>/',     ApproveUserView.as_view(),  name='auth_approve'),
    path('reject/<int:user_id>/',      RejectUserView.as_view(),   name='auth_reject'),
    path('revoke/<int:user_id>/',      RevokeUserView.as_view(),   name='auth_revoke'),
    path('role/<int:user_id>/',        UpdateRoleView.as_view(),   name='auth_role'),
    path('all/',                       AllUsersView.as_view(),     name='auth_all'),
]
