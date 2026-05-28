from django.urls import path
from .views import (
    RegisterView, LoginView, LogoutView, MeView,
    PendingUsersView, ApproveUserView, RejectUserView, AllUsersView,
    UpdateRoleView, RevokeUserView, UpdateUserView, WorksListView, AssignWorkView,
    ForgotPasswordView, MyWorksView,
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
    path('update/<int:user_id>/',      UpdateUserView.as_view(),   name='auth_update_user'),
    path('works/',                     WorksListView.as_view(),    name='auth_works_list'),
    path('assign-work/',               AssignWorkView.as_view(),   name='auth_assign_work'),
    path('my-works/',                  MyWorksView.as_view(),      name='auth_my_works'),
    path('forgot-password/',           ForgotPasswordView.as_view(), name='auth_forgot_password'),
]
