from django.db import models
from django.contrib.auth.models import User

class UserProfile(models.Model):
    ROLE_CHOICES = (
        ('observer', 'Observer'),
        ('consignee', 'Consignee'),
        ('executor', 'Executor'),
    )
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='work_profile')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='observer')

    def __str__(self):
        return f"{self.user.username} - {self.role}"

class Work(models.Model):
    loa_number = models.CharField(max_length=255, null=True, blank=True)
    tender_number = models.CharField(max_length=255, null=True, blank=True)
    date = models.CharField(max_length=255, null=True, blank=True)
    contract_agreement = models.CharField(max_length=255, null=True, blank=True)
    name_of_work = models.TextField(null=True, blank=True)
    contractor_name = models.CharField(max_length=255, null=True, blank=True)
    contractor_address = models.TextField(null=True, blank=True)
    date_of_completion = models.CharField(max_length=255, null=True, blank=True)
    consignee = models.CharField(max_length=255, null=True, blank=True)
    hrms_id = models.CharField(max_length=255, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.loa_number or 'Unknown Work'} - {self.contractor_name}"

class WorkItem(models.Model):
    work = models.ForeignKey(Work, on_delete=models.CASCADE, related_name='items')
    schedule = models.CharField(max_length=255, null=True, blank=True)
    serial_number = models.CharField(max_length=255, null=True, blank=True)
    category = models.CharField(max_length=100, null=True, blank=True)
    item_desc = models.TextField(null=True, blank=True)
    qty = models.FloatField(null=True, blank=True)
    unit = models.CharField(max_length=255, null=True, blank=True)
    unit_rate_rs = models.FloatField(null=True, blank=True)
    unit_rate_below = models.FloatField(null=True, blank=True)
    total_amount = models.FloatField(null=True, blank=True)

    technical_specification = models.CharField(max_length=255, null=True, blank=True)
    inspection_agency = models.CharField(max_length=255, null=True, blank=True)
    supplied_quantity = models.FloatField(null=True, blank=True)
    challan_no = models.CharField(max_length=255, null=True, blank=True)
    udm_entry = models.CharField(max_length=255, null=True, blank=True)
    
    executed_quantity = models.FloatField(null=True, blank=True, default=0)

    updated_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Item {self.serial_number} ({self.schedule})"


class WorkItemEntry(models.Model):
    """
    A single lot submission for a WorkItem.
    entry_type='supply'    → full inspection certificate data; updates WorkItem.supplied_quantity
    entry_type='execution' → quantity + location + remarks; updates WorkItem.executed_quantity
    Progress for Sch-A items uses supplied_quantity; Sch-B items use executed_quantity.
    """
    ENTRY_TYPE_CHOICES = (
        ('supply',    'Supply'),
        ('execution', 'Execution'),
    )
    work_item  = models.ForeignKey(WorkItem, on_delete=models.CASCADE, related_name='entries')
    entry_type = models.CharField(max_length=20, choices=ENTRY_TYPE_CHOICES, default='supply')
    quantity   = models.FloatField()

    # Supply — basic delivery details
    challan_no = models.CharField(max_length=255, blank=True, null=True)
    udm_entry  = models.CharField(max_length=255, blank=True, null=True)

    # Execution details
    location = models.CharField(max_length=500, blank=True, null=True)
    remarks  = models.TextField(blank=True, null=True)

    # Supply — Section 1: Material Supply Details
    specification_drawing_no = models.CharField(max_length=500, blank=True, null=True)
    other_details            = models.TextField(blank=True, null=True)

    # Supply — Section 2: Item Identification
    manufacturer_oem    = models.CharField(max_length=500, blank=True, null=True)
    trademark_batch_no  = models.CharField(max_length=500, blank=True, null=True)
    item_serial_no      = models.CharField(max_length=500, blank=True, null=True)
    manufacturing_date  = models.DateField(blank=True, null=True)
    visual_condition    = models.CharField(max_length=50, blank=True, null=True, default='OK')
    marking_on_material = models.CharField(max_length=500, blank=True, null=True)
    other_parameters    = models.TextField(blank=True, null=True)

    # Supply — Section 3: Technical Parameters (JSON list of {param, limit, result})
    electrical_parameters = models.JSONField(blank=True, null=True, default=list)
    mechanical_parameters = models.JSONField(blank=True, null=True, default=list)

    # Supply — Section 4: Inspection Summary
    total_offered            = models.FloatField(blank=True, null=True)
    total_passed             = models.FloatField(blank=True, null=True)
    total_rejected           = models.FloatField(blank=True, null=True)
    deviations_deficiencies  = models.TextField(blank=True, null=True)

    # Supply — Section 5: Declaration
    inspection_status            = models.CharField(max_length=20, blank=True, null=True, default='accepted')
    sample_test_officer_remarks  = models.TextField(blank=True, null=True)
    date_of_inspection           = models.DateField(blank=True, null=True)

    # Receipt identification (from DMTR / Receive Note)
    receive_note_no = models.CharField(max_length=255, blank=True, null=True)
    date_of_receipt = models.DateField(blank=True, null=True)

    submitted_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)
    submitted_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Lot {self.quantity} for Item {self.work_item_id}"


class WorkExtension(models.Model):
    """Time extensions granted when a work overshoots its completion date."""
    work = models.ForeignKey(Work, on_delete=models.CASCADE, related_name='extensions')
    extension_date = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"Extension for {self.work_id}: {self.extension_date}"
