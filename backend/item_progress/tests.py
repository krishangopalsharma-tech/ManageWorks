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
        UserProfile.objects.create(user=self.user, designation='JE', is_approved=True, role='consignee')

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
        # Search without q or work_ids -> empty paginated envelope
        response = self.client.get('/api/item-progress/search/')
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data['count'] == 0
        assert data['results'] == []
        assert 'stats' in data

        # Search with q matching item1 description
        response = self.client.get('/api/item-progress/search/?q=Copper')
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data['count'] == 1
        assert data['results'][0]['id'] == self.item1.pk
        assert data['results'][0]['loa_number'] == 'LOA-2026-X'

        # Search with work_ids filter
        response = self.client.get(f'/api/item-progress/search/?q=cable&work_ids={self.work.pk}')
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data['count'] == 1
        assert data['results'][0]['id'] == self.item1.pk

    def test_lean_fields_only(self):
        """Fields Item Progress never displays should be trimmed from the payload."""
        self.client.force_login(self.user)
        response = self.client.get(f'/api/item-progress/search/?work_ids={self.work.pk}')
        row = response.json()['results'][0]
        assert 'unit_rate_below' not in row
        assert 'unit_rate_rs' not in row
        assert 'total_amount' not in row
        assert 'technical_specification' not in row

    def test_pagination_pages_dont_repeat(self):
        self.client.force_login(self.user)
        response = self.client.get(f'/api/item-progress/search/?work_ids={self.work.pk}&page_size=1')
        data = response.json()
        assert data['count'] == 2
        assert len(data['results']) == 1
        assert data['next'] is not None

        page2 = self.client.get(data['next'].replace('http://testserver', ''))
        page2_data = page2.json()
        assert len(page2_data['results']) == 1
        assert page2_data['results'][0]['id'] != data['results'][0]['id']
        assert page2_data['next'] is None

    def test_category_filter_uncategorized_defaults_to_supply(self):
        """Neither fixture item has an explicit category — matches the frontend's
        `item.category || 'supply'` quirk: uncategorized items count as 'supply'
        for THIS filter (unlike the schedule-based fallback used for progress/stats),
        so both show up when filtering to 'supply'."""
        self.client.force_login(self.user)
        response = self.client.get(f'/api/item-progress/search/?work_ids={self.work.pk}&category=supply')
        data = response.json()
        assert data['count'] == 2

    def test_category_filter_discriminates_when_explicit(self):
        self.item2.category = 'execution'
        self.item2.save(update_fields=['category'])
        self.client.force_login(self.user)
        response = self.client.get(f'/api/item-progress/search/?work_ids={self.work.pk}&category=execution')
        data = response.json()
        assert data['count'] == 1
        assert data['results'][0]['id'] == self.item2.pk

    def test_progress_range_filter(self):
        """item1 is 20% (20/100), item2 is 40% (2/5) — filtering to 30-100% should drop item1."""
        self.client.force_login(self.user)
        response = self.client.get(
            f'/api/item-progress/search/?work_ids={self.work.pk}&progress_min=30&progress_max=100'
        )
        data = response.json()
        assert data['count'] == 1
        assert data['results'][0]['id'] == self.item2.pk

    def test_stats_match_expected(self):
        self.client.force_login(self.user)
        response = self.client.get(f'/api/item-progress/search/?work_ids={self.work.pk}')
        stats = response.json()['stats']
        # item1: supply, 20/100 = 20%. item2: schedule B / execution-style, 2/5 = 40%.
        assert stats['supplyPct'] == 20
        assert stats['execPct'] == 40
        assert stats['supplyCount'] == 1
        assert stats['execCount'] == 1

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
