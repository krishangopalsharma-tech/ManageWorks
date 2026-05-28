import pytest
from django.contrib.auth.models import User
from django.test import Client
from rest_framework import status
from works.models import Work, WorkItem
from mb_details.models import MBRecord, MBItem
from mb_details.parsers import _normalize_unit, _normalize_serial
from users.models import UserProfile

@pytest.mark.django_db
class TestMBDetails:

    @pytest.fixture(autouse=True)
    def setup_data(self):
        self.client = Client()
        
        # Create users
        self.admin = User.objects.create_superuser(username='admin', password='password123', email='admin@example.com')
        UserProfile.objects.create(user=self.admin, designation='Admin', pf_number='PF-ADM01', is_approved=True, role='admin')
        
        self.consignee1 = User.objects.create_user(username='consignee1', password='password123')
        UserProfile.objects.create(user=self.consignee1, designation='JE', pf_number='PF-CON1', is_approved=True, role='consignee')

        self.consignee2 = User.objects.create_user(username='consignee2', password='password123')
        UserProfile.objects.create(user=self.consignee2, designation='JE', pf_number='PF-CON2', is_approved=True, role='consignee')

        # Create works and items
        self.work1 = Work.objects.create(loa_number='LOA-2026-001', contractor_name='Apex', hrms_id='consignee1')
        self.item1 = WorkItem.objects.create(work=self.work1, serial_number='1.1', schedule='A', item_desc='Item A1', qty=100, unit_rate_below=10.0, total_amount=1000.0)
        self.item2 = WorkItem.objects.create(work=self.work1, serial_number='2.1', schedule='B', item_desc='Item B1', qty=50, unit_rate_below=20.0, total_amount=1000.0)

        self.work2 = Work.objects.create(loa_number='LOA-2026-002', contractor_name='Builders', hrms_id='consignee2')

    def test_mb_record_list(self):
        self.client.force_login(self.consignee1)
        response = self.client.get('/api/mb-details/records/?work_id=' + str(self.work1.pk))
        assert response.status_code == status.HTTP_200_OK

    def test_mb_record_create_admin_blocked(self):
        self.client.force_login(self.admin)
        response = self.client.post('/api/mb-details/records/', {
            'work': self.work1.pk,
            'mb_number': 'MB-999',
            'items': [{'work_item': self.item1.pk, 'quantity': 10, 'current_percentage': 50}]
        }, content_type='application/json')
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_mb_record_create_consignee(self):
        self.client.force_login(self.consignee1)
        response = self.client.post('/api/mb-details/records/', {
            'work': self.work1.pk,
            'mb_number': 'MB-101',
            'notes': 'Test notes',
            'items': [{'work_item': self.item1.pk, 'quantity': 50, 'current_percentage': 100}]
        }, content_type='application/json')
        assert response.status_code == status.HTTP_201_CREATED
        
        # Verify DB entry
        record = MBRecord.objects.get(work=self.work1, mb_number='MB-101')
        assert record.created_by == self.consignee1
        assert MBItem.objects.filter(mb_record=record).count() == 1
        
        # Verify auto-calculated amount
        mb_item = MBItem.objects.get(mb_record=record, work_item=self.item1)
        assert mb_item.amount == 50 * 10.0 * 1.0  # qty * rate * percent/100 -> 50 * 10 * 1 = 500

    def test_mb_record_delete(self):
        self.client.force_login(self.consignee1)
        
        # First create MBRecord
        record = MBRecord.objects.create(work=self.work1, mb_number='MB-102', created_by=self.consignee1)
        MBItem.objects.create(mb_record=record, work_item=self.item1, quantity=10, current_percentage=50)
        
        response = self.client.delete(f'/api/mb-details/records/{record.pk}/')
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not MBRecord.objects.filter(pk=record.pk).exists()

    def test_mb_record_patch_amount(self):
        self.client.force_login(self.consignee1)
        
        record = MBRecord.objects.create(work=self.work1, mb_number='MB-103', created_by=self.consignee1)
        mb_item = MBItem.objects.create(mb_record=record, work_item=self.item1, quantity=10, current_percentage=50)
        assert mb_item.amount == 50.0  # 10 * 10.0 * 50 / 100

        # Patch item details
        response = self.client.patch(f'/api/mb-details/records/{record.pk}/', {
            'mb_number': 'MB-103-UPDATED',
            'items': [{'work_item': self.item1.pk, 'quantity': 20, 'current_percentage': 100}]
        }, content_type='application/json')
        assert response.status_code == status.HTTP_200_OK
        
        # Verify MB number changed and amount updated
        record.refresh_from_db()
        assert record.mb_number == 'MB-103-UPDATED'
        
        mb_item_up = MBItem.objects.get(mb_record=record, work_item=self.item1)
        assert mb_item_up.quantity == 20
        assert mb_item_up.amount == 200.0  # 20 * 10.0 * 100 / 100

    def test_mb_summary(self):
        self.client.force_login(self.consignee1)
        
        # Create billing on Sch A and Sch B
        record = MBRecord.objects.create(work=self.work1, mb_number='MB-104', created_by=self.consignee1)
        MBItem.objects.create(mb_record=record, work_item=self.item1, quantity=20, current_percentage=100) # Amount: 200.0 (Sch A)
        MBItem.objects.create(mb_record=record, work_item=self.item2, quantity=10, current_percentage=50)  # Amount: 100.0 (Sch B)
        
        response = self.client.get(f'/api/mb-details/summary/?work_id={self.work1.pk}')
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data['total_work_amount'] == 2000.0  # item1 total + item2 total
        assert data['mb_total'] == 30000.0 / 100.0  # 300.0
        assert data['financial_progress'] == 15.0   # 300 / 2000
        assert data['sch_a_billed'] == 200.0
        assert data['sch_b_billed'] == 100.0

    def test_pdf_import_invalid_format(self):
        self.client.force_login(self.consignee1)
        response = self.client.post('/api/mb-details/import-pdf/', {
            'file': 'not-a-pdf-file-content'
        })
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_check_work_access_consignee_other(self):
        # consignee1 tries to search items of work2 (assigned to consignee2) -> 403 Forbidden
        self.client.force_login(self.consignee1)
        response = self.client.get(f'/api/mb-details/works/{self.work2.pk}/items/')
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_normalize_unit(self):
        assert _normalize_unit('Runnin g  Metre') == 'Running Metre'
        assert _normalize_unit('Lumpsu m') == 'Lumpsum'
        assert _normalize_unit('Nos') == 'Nos'

    def test_normalize_serial(self):
        assert _normalize_serial('01') == '1'
        assert _normalize_serial('01.0') == '1'
        assert _normalize_serial('A.1.1') == 'A.1.1'
