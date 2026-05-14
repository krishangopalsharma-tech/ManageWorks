from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),

    # Core data app (models only — no active endpoints)
    path('api/works/', include('works.urls')),

    # Feature apps — one per page
    path('api/dashboard/', include('dashboard.urls')),
    path('api/work-details/', include('work_details.urls')),
    path('api/update-work/', include('update_work.urls')),
    path('api/add-work/', include('add_work.urls')),
    path('api/documents/', include('documents.urls')),
    path('api/auth/', include('users.urls')),
    path('api/item-progress/', include('item_progress.urls')),
    path('api/mb-details/', include('mb_details.urls')),
    path('api/installation-cert/', include('installation_cert.urls')),
    path('api/site-register/',    include('site_register.urls')),
    path('api/settings/site-gsheet/', include('site_gsheet_settings.urls')),
]
