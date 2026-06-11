from rest_framework import serializers
from .models import BillRecord, BillItem


class BillItemSerializer(serializers.ModelSerializer):
    contract_value = serializers.SerializerMethodField()
    progress_pct   = serializers.SerializerMethodField()

    class Meta:
        model  = BillItem
        fields = [
            'id', 'schedule_name', 'item_number', 'description',
            'unit', 'agreement_rate', 'current_agmt_qty', 'qty_upto_date',
            'amt_total', 'contract_value', 'progress_pct',
        ]

    def get_contract_value(self, obj):
        return obj.contract_value

    def get_progress_pct(self, obj):
        return obj.progress_pct


class BillRecordSerializer(serializers.ModelSerializer):
    items            = BillItemSerializer(many=True, read_only=True)
    uploaded_by_name = serializers.SerializerMethodField()

    class Meta:
        model  = BillRecord
        fields = [
            'id', 'bill_number', 'bill_date', 'loa_number',
            'agreement_number', 'uploaded_by_name', 'uploaded_at',
            'total_amount_override', 'items',
        ]

    def get_uploaded_by_name(self, obj):
        if obj.uploaded_by:
            return obj.uploaded_by.get_full_name() or obj.uploaded_by.username
        return ''
