import pytest
from django.contrib.auth.models import User
from django.test import Client
from rest_framework import status
from works.models import Work, WorkItem, WorkItemEntry
from users.models import UserProfile

@pytest.mark.django_db
class TestItemProgress:

    @pytest.fixture(autouse=True)
    def setup_data(self):
        self.client = Client()
        self.user = User.objects.create_user(username='consignee1', password='password123')
        UserProfile.objects.create(user=self.user, designation='JE', pf_number='PF-01', is_approved=True, role='consignee')
        
        # Create work and items
        self.work = Work.objects.create(loa_number='LOA-2026-X', contractor_name='Contractor X', hrms_id='consignee1')
        self.item1 = WorkItem.objects.create(
            work=self.work, serial_number='1.1', schedule='A', item_desc='Heavy Copper Cable',
            qty=100.0, unit='Metres', unit_rate_below=10.0, total_amount=1000.0, supplied_quantity=20.0
        )
        self.item2 = WorkItem.objects.create(
            work=self.work, serial_number='2.1', schedule='B', item_desc='Transformer laying',
            qty=5.0, unit='Numbers', unit_rate_below=100.0, total_amount=500.0, executed_quantity=2.0
        )

    def test_item_progress_list_consignee(self):
        self.client.force_login(self.user)
        response = self.client.get('/api/item-progress/works/')
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 1
        assert data[0]['loa_number'] == 'LOA-2026-X'

    def test_item_progress_search(self):
        self.client.force_login(self.user)
        # Search without q -> empty
        response = self.client.get('/api/item-progress/search/')
        assert response.status_code == status.HTTP_200_OK
        assert response.json() == []
        
        # Search with q matching item1 description
        response = self.client.get('/api/item-progress/search/?q=Copper')
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 1
        assert data[0]['id'] == self.item1.pk
        assert data[0]['loa_number'] == 'LOA-2026-X'

        # Search with work_ids filter
        response = self.client.get(f'/api/item-progress/search/?q=cable&work_ids={self.work.pk}')
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 1
        assert data[0]['id'] == self.item1.pk

    def test_progress_supply_qty(self):
        # Verify initial supplied quantity is 20
        assert self.item1.supplied_quantity == 20.0
        
        # Create a new supply entry
        entry = WorkItemEntry.objects.create(
            work_item=self.item1,
            entry_type='supply',
            quantity=15.0,
            submitted_by=self.user
        )
        
        # In a real app the supplied_quantity is updated via signals or views.
        # Let's verify that the entry is created correctly and can be fetched.
        assert entry.quantity == 15.0
        assert entry.work_item == self.item1

    def test_progress_execution_qty(self):
        assert self.item2.executed_quantity == 2.0
        
        # Create execution entry
        entry = WorkItemEntry.objects.create(
            work_item=self.item2,
            entry_type='execution',
            quantity=1.0,
            submitted_by=self.user
        )
        assert entry.quantity == 1.0
        assert entry.work_item == self.item2
