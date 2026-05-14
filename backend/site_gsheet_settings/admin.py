from django.contrib import admin
from .models import SiteGSheet


@admin.register(SiteGSheet)
class SiteGSheetAdmin(admin.ModelAdmin):
    list_display  = ('name', 'sheet_id', 'is_active', 'created_at')
    list_editable = ('is_active',)
    search_fields = ('name',)
    readonly_fields = ('sheet_id', 'created_at', 'updated_at')
