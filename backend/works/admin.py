from django.contrib import admin
from .models import Work, WorkItem, UserProfile


@admin.register(Work)
class WorkAdmin(admin.ModelAdmin):
    list_display = ('loa_number', 'tender_number', 'contractor_name', 'date_of_completion', 'created_at')
    search_fields = ('loa_number', 'tender_number', 'contractor_name')


@admin.register(WorkItem)
class WorkItemAdmin(admin.ModelAdmin):
    list_display = ('work', 'schedule', 'serial_number', 'item_desc', 'qty', 'supplied_quantity', 'updated_by', 'updated_at')
    list_filter = ('schedule',)
    search_fields = ('item_desc', 'challan_no')


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'role')
    list_filter = ('role',)
