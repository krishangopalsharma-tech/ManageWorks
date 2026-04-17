from rest_framework import serializers
from .models import Work, WorkItem, WorkItemEntry
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

class WorkSerializer(serializers.ModelSerializer):
    items = WorkItemSerializer(many=True, read_only=True)

    class Meta:
        model = Work
        fields = '__all__'


class WorkEditSerializer(serializers.ModelSerializer):
    class Meta:
        model = Work
        fields = [
            'id', 'loa_number', 'tender_number', 'date',
            'contract_agreement', 'contractor_name',
            'contractor_address', 'date_of_completion', 'consignee',
        ]
