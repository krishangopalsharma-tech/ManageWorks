from django.db import models
from django.contrib.auth.models import User
from works.models import Work


class BillRecord(models.Model):
    work             = models.ForeignKey(Work, on_delete=models.CASCADE, related_name='bill_records')
    bill_number      = models.CharField(max_length=200)
    bill_date        = models.DateField(null=True, blank=True)
    loa_number       = models.CharField(max_length=200, blank=True)
    agreement_number = models.CharField(max_length=200, blank=True)
    uploaded_by      = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)
    uploaded_at      = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['bill_date', 'bill_number']

    def __str__(self):
        return f"{self.bill_number} ({self.bill_date})"


class BillItem(models.Model):
    bill_record      = models.ForeignKey(BillRecord, on_delete=models.CASCADE, related_name='items')
    schedule_name    = models.CharField(max_length=50)   # A1, B3, etc.
    item_number      = models.CharField(max_length=20)   # 1, 10, 12, etc.
    description      = models.TextField(blank=True)
    unit             = models.CharField(max_length=100, blank=True)
    agreement_rate   = models.FloatField(default=0)
    current_agmt_qty = models.FloatField(default=0)
    qty_upto_date    = models.FloatField(default=0)      # col 9: Qty Upto Date (executed)
    amt_total        = models.FloatField(default=0)      # Total Up to Date Amount

    class Meta:
        ordering = ['schedule_name', 'item_number']

    @property
    def contract_value(self):
        return round(self.current_agmt_qty * self.agreement_rate, 2)

    @property
    def progress_pct(self):
        cv = self.contract_value
        if not cv:
            return 0.0
        return round(min(self.amt_total / cv * 100, 100), 1)

    def __str__(self):
        return f"Sch {self.schedule_name} Item {self.item_number}"
