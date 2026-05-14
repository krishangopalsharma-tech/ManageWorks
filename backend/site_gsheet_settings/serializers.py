from rest_framework import serializers
from .models import SiteGSheet


class SiteGSheetSerializer(serializers.ModelSerializer):
    class Meta:
        model  = SiteGSheet
        fields = ['id', 'name', 'sheet_url', 'sheet_id', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['sheet_id', 'created_at', 'updated_at']
