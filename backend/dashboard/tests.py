import pytest
from django.contrib.auth.models import User
from django.test import Client
from django.utils import timezone
from datetime import timedelta
from rest_framework import status
from works.models import Work, WorkItem, WorkItemEntry
from mb_details.models import MBRecord, MBItem
from users.models import UserProfile

@pytest.mark.django_db
class TestDashboard:

    @pytest.fixture(autouse=True)
    def setup_data(self):
        self.client = Client()
        
        # Create users
        self.admin = User.objects.create_superuser(username='admin', password='password123', email='admin@example.com')
        UserProfile.objects.create(user=self.admin, designation='Admin', pf_number='PF-ADM01', is_approved=True, role='admin')
        
        self.consignee = User.objects.create_user(username='consignee1', password='password123')
        UserProfile.objects.create(user=self.consignee, designation='JE', pf_number='PF-CON1', is_approved=True, role='consignee')

        # Create works, items, and entries
        self.work1 = Work.objects.create(loa_number='LOA-2026-001', contractor_name='Apex', hrms_id='consignee1')
        
        # Schedule A (Supply) item
        self.item_a = WorkItem.objects.create(
            work=self.work1, serial_number='1.1', schedule='A', item_desc='Supply cable',
            qty=100.0, unit_rate_below=10.0, total_amount=1000.0, supplied_quantity=50.0
        )
        # Schedule B (Execution) item
        self.item_b = WorkItem.objects.create(
            work=self.work1, serial_number='2.1', schedule='B', item_desc='Install cable',
            qty=50.0, unit_rate_below=20.0, total_amount=1000.0, executed_quantity=25.0
        )

        # Create MB and MB item billing
        self.record = MBRecord.objects.create(work=self.work1, mb_number='MB-301', created_by=self.consignee)
        MBItem.objects.create(mb_record=self.record, work_item=self.item_a, quantity=30.0, current_percentage=100) # Amount: 300

    def test_dashboard_stats_admin(self):
        self.client.force_login(self.admin)
        response = self.client.get('/api/dashboard/')
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        # supply avg = 50 / 100 * 100 = 50%
        # execution avg = 25 / 50 * 100 = 50%
        # overall avg = (0.5 + 0.5) / 2 * 100 = 50%
        # financial prog = 300 / 2000 * 100 = 15%
        assert data['supply'] == 50.0
        assert data['execution'] == 50.0
        assert data['overall'] == 50.0
        assert data['financial'] == 15.0
        assert len(data['loas']) == 1

    def test_dashboard_stats_consignee(self):
        self.client.force_login(self.consignee)
        response = self.client.get(f'/api/dashboard/?loa_id={self.work1.pk}')
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data['supply'] == 50.0
        assert data['overall'] == 50.0

    def test_dashboard_trend_daily(self):
        # Create some WorkItemEntry objects to drive progress trends
        WorkItemEntry.objects.create(
            work_item=self.item_a,
            entry_type='supply',
            quantity=10,
            submitted_at=timezone.now() - timedelta(days=2)
        )
        WorkItemEntry.objects.create(
            work_item=self.item_b,
            entry_type='execution',
            quantity=5,
            submitted_at=timezone.now() - timedelta(days=1)
        )
        
        self.client.force_login(self.consignee)
        response = self.client.get(f'/api/dashboard/trend/?period=daily&loa_id={self.work1.pk}')
        assert response.status_code == status.HTTP_200_OK
        
        data = response.json()
        assert isinstance(data, list)
        if len(data) > 0:
            assert 'supply' in data[0]
            assert 'execution' in data[0]
            assert 'financial' in data[0]

    def test_dashboard_trend_invalid_period(self):
        self.client.force_login(self.consignee)
        # Should fallback gracefully to 'monthly' when given invalid period
        response = self.client.get(f'/api/dashboard/trend/?period=invalid_period&loa_id={self.work1.pk}')
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert isinstance(data, list)
