from django.db import models
from django.contrib.auth.models import User
from works.models import Work, WorkItem


class MBRecord(models.Model):
    """A Measurement Book. Holds line items billed (can mix Sch A and Sch B)."""
    work             = models.ForeignKey(Work, on_delete=models.CASCADE, related_name='mb_records')
    mb_number        = models.CharField(max_length=500, help_text='User-entered MB number/reference (free text)')
    measurement_date = models.DateField(null=True, blank=True, help_text='Date of measurement as recorded in the MB')
    notes            = models.TextField(blank=True, null=True)
    created_by       = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)
    created_at       = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['work_id', 'mb_number']
        unique_together = [('work', 'mb_number')]

    def __str__(self):
        return f"MB{self.mb_number} · Work {self.work_id}"


class MBItem(models.Model):
    """
    A single line in an MB: item + quantity + current payment % → released amount.

    Released amount = quantity * unit_rate_below * current_percentage / 100
    """
    mb_record          = models.ForeignKey(MBRecord, on_delete=models.CASCADE, related_name='items')
    work_item          = models.ForeignKey(WorkItem, on_delete=models.CASCADE, related_name='mb_items')
    quantity           = models.FloatField(help_text='Qty of this item billed in this line')
    current_percentage = models.FloatField(help_text='Payment % for this MB')
    amount             = models.FloatField(default=0, help_text='Auto: qty × rate × current_percentage / 100')

    class Meta:
        ordering = ['id']

    def save(self, *args, **kwargs):
        rate = self.work_item.unit_rate_below or 0
        qty  = self.quantity or 0
        self.amount = round(qty * rate * (self.current_percentage or 0) / 100, 2)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"MBItem item={self.work_item_id} qty={self.quantity} {self.current_percentage}%"
