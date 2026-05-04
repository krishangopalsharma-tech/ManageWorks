from rest_framework import serializers
from .models import Work, WorkItem, WorkItemEntry, WorkExtension
from django.contrib.auth.models import User

class UserSerializer(serializers.ModelSerializer):
    role = serializers.CharField(source='profile.role', read_only=True)
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'role']

class WorkItemEntrySerializer(serializers.ModelSerializer):
    submitted_by_user = UserSerializer(source='submitted_by', read_only=True)
    class Meta:
        model = WorkItemEntry
        fields = '__all__'

class WorkItemSerializer(serializers.ModelSerializer):
    updated_by_user = UserSerializer(source='updated_by', read_only=True)
    entries = WorkItemEntrySerializer(many=True, read_only=True)
    class Meta:
        model = WorkItem
        fields = '__all__'

class WorkExtensionSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkExtension
        fields = ['id', 'extension_date']

class WorkSerializer(serializers.ModelSerializer):
    items = WorkItemSerializer(many=True, read_only=True)
    extensions = WorkExtensionSerializer(many=True, read_only=True)
    mb_billing = serializers.SerializerMethodField()

    class Meta:
        model = Work
        fields = '__all__'

    def get_mb_billing(self, obj):
        return [
            {
                'date': str(mb.measurement_date) if mb.measurement_date else None,
                'amount': round(sum(item.amount or 0 for item in mb.items.all()), 2),
                'mb_number': mb.mb_number,
            }
            for mb in obj.mb_records.all()
            if mb.measurement_date
        ]


class WorkEditSerializer(serializers.ModelSerializer):
    class Meta:
        model = Work
        fields = [
            'id', 'loa_number', 'tender_number', 'date',
            'contract_agreement', 'name_of_work', 'contractor_name',
            'contractor_address', 'date_of_completion', 'consignee',
        ]
