from django.urls import path
from .views import (
    SiteRegisterView,
    TelegramOTPView, TelegramUnlinkView,
    LoaPartiesListView, LinkedUsersView, LoaPartyView,
    SupervisorInviteView,
    RlyLinkedUsersView, RlyOfficialInviteView,
    ThreadStatsView,
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

    path('rly-linked-users/',              RlyLinkedUsersView.as_view(), name='rly_linked_users'),
    path('rly-linked-users/<int:link_id>/', RlyLinkedUsersView.as_view(), name='rly_linked_user_detail'),
    path('rly-invite/',              RlyOfficialInviteView.as_view(), name='rly_invite_create'),
    path('rly-invite/<str:code>/',   RlyOfficialInviteView.as_view(), name='rly_invite_status'),

    path('thread-stats/', ThreadStatsView.as_view(), name='thread_stats'),
]
