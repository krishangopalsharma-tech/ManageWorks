from rest_framework import serializers
from .models import MBRecord, MBItem


class MBItemSerializer(serializers.ModelSerializer):
    work_item_desc     = serializers.CharField(source='work_item.item_desc',        read_only=True)
    work_item_sno      = serializers.CharField(source='work_item.serial_number',    read_only=True)
    work_item_sch      = serializers.CharField(source='work_item.schedule',         read_only=True)
    work_item_qty      = serializers.FloatField(source='work_item.qty',             read_only=True)
    work_item_unit     = serializers.CharField(source='work_item.unit',             read_only=True)
    work_item_rate     = serializers.FloatField(source='work_item.unit_rate_below', read_only=True)
    work_item_total    = serializers.FloatField(source='work_item.total_amount',    read_only=True)

    class Meta:
        model  = MBItem
        fields = ['id', 'work_item',
                  'quantity', 'prior_percentage', 'current_percentage', 'amount',
                  'work_item_desc', 'work_item_sno', 'work_item_sch',
                  'work_item_qty', 'work_item_unit', 'work_item_rate', 'work_item_total']
        read_only_fields = ['amount']


class MBRecordSerializer(serializers.ModelSerializer):
    items          = MBItemSerializer(many=True, read_only=True)
    work_loa       = serializers.CharField(source='work.loa_number',      read_only=True)
    work_tender    = serializers.CharField(source='work.tender_number',   read_only=True)
    contractor     = serializers.CharField(source='work.contractor_name', read_only=True)
    work_name      = serializers.CharField(source='work.name_of_work',    read_only=True)
    created_by_username = serializers.CharField(source='created_by.username', read_only=True)
    total_amount   = serializers.SerializerMethodField()

    class Meta:
        model  = MBRecord
        fields = ['id', 'work', 'mb_number', 'measurement_date', 'notes',
                  'work_loa', 'work_tender', 'contractor', 'work_name',
                  'created_by_username', 'created_at',
                  'items', 'total_amount']
        read_only_fields = ['created_at']

    def get_total_amount(self, obj):
        return round(sum(i.amount or 0 for i in obj.items.all()), 2)
