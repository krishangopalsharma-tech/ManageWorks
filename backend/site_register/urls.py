from django.urls import path
from .views import (
    SiteRegisterView,
    TelegramOTPView, TelegramUnlinkView,
    LoaPartiesListView, LinkedUsersView, LoaPartyView,
    SupervisorInviteView,
)

urlpatterns = [
    path('', SiteRegisterView.as_view(), name='site_register'),
    path('telegram/otp/',    TelegramOTPView.as_view(),    name='telegram_otp'),
    path('telegram/unlink/', TelegramUnlinkView.as_view(), name='telegram_unlink'),

    path('parties/',                               LoaPartiesListView.as_view(), name='loa_parties_list'),
    path('linked-users/',                          LinkedUsersView.as_view(),    name='linked_users'),
    path('linked-users/<int:link_id>/',            LinkedUsersView.as_view(),    name='linked_user_edit'),
    path('parties/<int:work_id>/',                 LoaPartyView.as_view(),       name='loa_party_add'),
    path('parties/<int:work_id>/<int:mapping_id>/', LoaPartyView.as_view(),      name='loa_party_delete'),

    path('supervisor-invite/',              SupervisorInviteView.as_view(), name='supervisor_invite_create'),
    path('supervisor-invite/<str:code>/',   SupervisorInviteView.as_view(), name='supervisor_invite_status'),
]
