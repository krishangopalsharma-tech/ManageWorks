from django.db import models
from django.contrib.auth.models import User

class UserProfile(models.Model):
    ROLE_CHOICES = (
        ('observer', 'Observer'),
        ('consignee', 'Consignee'),
        ('executor', 'Executor'),
    )
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='observer')

    def __str__(self):
        return f"{self.user.username} - {self.role}"

class Work(models.Model):
    loa_number = models.CharField(max_length=255, null=True, blank=True)
    tender_number = models.CharField(max_length=255, null=True, blank=True)
    date = models.CharField(max_length=255, null=True, blank=True)
    contract_agreement = models.CharField(max_length=255, null=True, blank=True)
    contractor_name = models.CharField(max_length=255, null=True, blank=True)
    contractor_address = models.TextField(null=True, blank=True)
    date_of_completion = models.CharField(max_length=255, null=True, blank=True)
    consignee = models.CharField(max_length=255, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.loa_number or 'Unknown Work'} - {self.contractor_name}"

class WorkItem(models.Model):
    work = models.ForeignKey(Work, on_delete=models.CASCADE, related_name='items')
    schedule = models.CharField(max_length=255, null=True, blank=True)
    serial_number = models.CharField(max_length=255, null=True, blank=True)
    item_desc = models.TextField(null=True, blank=True)
    qty = models.FloatField(null=True, blank=True)
    unit = models.CharField(max_length=255, null=True, blank=True)
    unit_rate_rs = models.FloatField(null=True, blank=True)
    unit_rate_below = models.FloatField(null=True, blank=True)
    total_amount = models.FloatField(null=True, blank=True)

    technical_specification = models.CharField(max_length=255, null=True, blank=True)
    supplied_quantity = models.FloatField(null=True, blank=True)
    challan_no = models.CharField(max_length=255, null=True, blank=True)
    udm_entry = models.CharField(max_length=255, null=True, blank=True)
    
    updated_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Item {self.serial_number} ({self.schedule})"


class WorkItemEntry(models.Model):
    """
    A single lot submission for a WorkItem.
    Contractors/executors may submit multiple lots against the same item.
    The WorkItem.supplied_quantity is kept in sync as the running sum of all entries.
    """
    work_item = models.ForeignKey(WorkItem, on_delete=models.CASCADE, related_name='entries')
    quantity = models.FloatField()
    challan_no = models.CharField(max_length=255, blank=True, null=True)
    udm_entry = models.CharField(max_length=255, blank=True, null=True)
    submitted_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)
    submitted_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Lot {self.quantity} for Item {self.work_item_id}"
