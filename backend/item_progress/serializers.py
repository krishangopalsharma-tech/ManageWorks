from rest_framework import serializers
from works.models import WorkItem, WorkItemEntry
from works.serializers import UserSerializer


class ItemProgressEntrySerializer(serializers.ModelSerializer):
    """Lean entry serializer for Item Progress — only the fields this page
    actually renders (see ItemProgress.vue's expanded-row table and PDF
    export), unlike works.serializers.WorkItemEntrySerializer's fields='__all__'
    which also carries the full supply-inspection form (electrical/mechanical
    parameter JSON blobs, deviation notes, etc.) that this page never shows."""
    submitted_by_user = UserSerializer(source='submitted_by', read_only=True)
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
        fields = [
            'id', 'entry_type', 'quantity', 'receive_note_no', 'challan_no',
            'udm_entry', 'location', 'date_of_receipt', 'submitted_at',
            'submitted_by', 'submitted_by_user', 'submitted_by_designation_display',
        ]


class ItemProgressItemSerializer(serializers.ModelSerializer):
    """Lean item serializer for Item Progress — drops fields this page never
    displays (unit_rate_rs, unit_rate_below, total_amount, technical_specification,
    inspection_agency) that works.serializers.WorkItemSerializer's fields='__all__'
    carries for pages that do need them (e.g. Work Details)."""
    entries = ItemProgressEntrySerializer(many=True, read_only=True)

    class Meta:
        model = WorkItem
        fields = [
            'id', 'schedule', 'serial_number', 'category', 'item_desc',
            'qty', 'unit', 'supplied_quantity', 'executed_quantity', 'entries',
        ]
