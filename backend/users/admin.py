from django.contrib import admin
from .models import UserProfile


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display  = ('user', 'designation', 'is_approved', 'role', 'created_at')
    list_filter   = ('is_approved', 'role')
    search_fields = ('user__username', 'user__first_name')
    actions       = ['approve_users']

    def approve_users(self, request, queryset):
        queryset.update(is_approved=True)
    approve_users.short_description = 'Approve selected users'
