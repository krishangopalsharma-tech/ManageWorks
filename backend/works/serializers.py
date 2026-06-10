from rest_framework import serializers
from .models import Work, WorkItem, WorkItemEntry, WorkExtension
from .utils import contractor_nickname as _nickname
from django.contrib.auth.models import User

class UserSerializer(serializers.ModelSerializer):
    role = serializers.CharField(source='profile.role', read_only=True)
    designation = serializers.CharField(source='profile.designation', read_only=True)
    full_name = serializers.SerializerMethodField()

    def get_full_name(self, obj):
        name = f"{obj.first_name} {obj.last_name}".strip()
        return name or obj.username

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'role', 'full_name', 'designation']

class WorkItemEntrySerializer(serializers.ModelSerializer):
    submitted_by_user = UserSerializer(source='submitted_by', read_only=True)
    # Returns snapshotted designation; falls back to live profile if snapshot missing (legacy rows)
    submitted_by_designation_display = serializers.SerializerMethodField()

    def get_submitted_by_designation_display(self, obj):
        if obj.submitted_by_designation:
            return obj.submitted_by_designation
        try:
            return obj.submitted_by.profile.designation
        except Exception:
            return None

    class Meta:
        model = WorkItemEntry
        fields = '__all__'

class WorkItemSerializer(serializers.ModelSerializer):
    updated_by_user = UserSerializer(source='updated_by', read_only=True)
    updated_by_designation_display = serializers.SerializerMethodField()
    entries = WorkItemEntrySerializer(many=True, read_only=True)

    def get_updated_by_designation_display(self, obj):
        if obj.updated_by_designation:
            return obj.updated_by_designation
        try:
            return obj.updated_by.profile.designation
        except Exception:
            return None

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
    bill_billing = serializers.SerializerMethodField()
    contractor_nickname = serializers.SerializerMethodField()
    consignee_display = serializers.SerializerMethodField()

    class Meta:
        model = Work
        fields = '__all__'

    def get_contractor_nickname(self, obj):
        return _nickname(obj.contractor_name or '')

    def get_consignee_display(self, obj):
        if obj.hrms_id:
            try:
                user = User.objects.get(username=obj.hrms_id)
                name = user.first_name or obj.hrms_id
                designation = getattr(user, 'profile', None)
                designation = designation.designation if designation else None
                if name and designation:
                    return f"{name} ({designation})"
                return name or designation or obj.consignee or ''
            except User.DoesNotExist:
                pass
        return obj.consignee or ''

    def get_bill_billing(self, obj):
        from financial_progress.models import BillItem
        from django.db.models import Sum as _Sum
        # Sum all bills' period amounts (not latest-only) for true cumulative
        total_paid = BillItem.objects.filter(bill_record__work_id=obj.id).aggregate(t=_Sum('amt_total'))['t'] or 0

        bills = list(obj.bill_records.prefetch_related('items').order_by('bill_date', 'id'))
        bills_data = [
            {
                'date':        str(bill.bill_date) if bill.bill_date else None,
                'amount':      round(sum(i.amt_total or 0 for i in bill.items.all()), 2),
                'bill_number': bill.bill_number,
            }
            for bill in bills
            if bill.bill_date
        ]
        return {'total_paid': round(total_paid, 2), 'bills': bills_data}


class WorkEditSerializer(serializers.ModelSerializer):
    class Meta:
        model = Work
        fields = [
            'id', 'loa_number', 'tender_number', 'date',
            'contract_agreement', 'name_of_work', 'contractor_name',
            'contractor_address', 'date_of_completion', 'consignee', 'hrms_id',
        ]
