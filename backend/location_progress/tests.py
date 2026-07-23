import pytest
from django.contrib.auth.models import User
from django.test import Client
from rest_framework import status
from works.models import Work, WorkItem, WorkItemEntry
from users.models import UserProfile


@pytest.mark.django_db
class TestLocationProgress:
    """The riskiest piece of the pagination rework — grouping raw execution
    entries into (location, work_item) buckets at the DB level so pagination
    can operate on the grouped rows, not the raw entries."""

    @pytest.fixture(autouse=True)
    def setup_data(self):
        self.client = Client()
        self.user = User.objects.create_user(username='consignee1', password='password123')
        UserProfile.objects.create(user=self.user, designation='JE', is_approved=True, role='consignee')

        self.other = User.objects.create_user(username='consignee2', password='password123')
        UserProfile.objects.create(user=self.other, designation='JE2', is_approved=True, role='consignee')

        self.work = Work.objects.create(loa_number='LOA-LP-001', contractor_name='Contractor Y', hrms_id='consignee1')

        self.item_exec = WorkItem.objects.create(
            work=self.work, schedule='B', serial_number='1', category='execution',
            item_desc='Cable laying', qty=100.0, unit='Metres', executed_quantity=30.0,
        )
        self.item_si = WorkItem.objects.create(
            work=self.work, schedule='A1', serial_number='2', category='supply_installation',
            item_desc='Signal installation', qty=10.0, unit='Numbers', executed_quantity=4.0,
        )

        # Two entries at the same location (ADI) on item_exec — should group into one bucket
        WorkItemEntry.objects.create(
            work_item=self.item_exec, entry_type='execution', quantity=20.0,
            location='ADI', submitted_by=self.user,
        )
        WorkItemEntry.objects.create(
            work_item=self.item_exec, entry_type='execution', quantity=10.0,
            location='adi', submitted_by=self.other,  # lowercase — must normalise to same bucket
        )
        # A different location on the same item — separate bucket
        WorkItemEntry.objects.create(
            work_item=self.item_exec, entry_type='execution', quantity=5.0,
            location='ASV-NRD', submitted_by=self.user,
        )
        # S+I item at its own location
        WorkItemEntry.objects.create(
            work_item=self.item_si, entry_type='execution', quantity=4.0,
            location='BRC', submitted_by=self.user,
        )
        # A supply entry (not execution) must never show up here at all
        WorkItemEntry.objects.create(
            work_item=self.item_exec, entry_type='supply', quantity=99.0,
            submitted_by=self.user,
        )

    def test_groups_by_location_and_item(self):
        self.client.force_login(self.user)
        response = self.client.get(f'/api/location-progress/data/?work_ids={self.work.pk}')
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        # 3 buckets: (ADI, item_exec), (ASV-NRD, item_exec), (BRC, item_si)
        assert data['count'] == 3
        adi_row = next(r for r in data['results'] if r['location'] == 'ADI')
        assert adi_row['executed_here'] == 30.0  # 20 + 10, case-insensitively grouped
        assert adi_row['entries_count'] == 2
        assert adi_row['scope'] == 100.0
        assert adi_row['total_executed'] == 30.0  # WorkItem's own cumulative total, not just this location

    def test_supply_entries_excluded(self):
        self.client.force_login(self.user)
        response = self.client.get(f'/api/location-progress/data/?work_ids={self.work.pk}')
        data = response.json()
        total_entries = sum(r['entries_count'] for r in data['results'])
        assert total_entries == 4  # the 99.0 supply entry must not appear anywhere

    def test_pagination_pages_dont_repeat(self):
        self.client.force_login(self.user)
        response = self.client.get(f'/api/location-progress/data/?work_ids={self.work.pk}&page_size=1')
        data = response.json()
        assert data['count'] == 3
        assert len(data['results']) == 1
        assert data['next'] is not None

        seen = {data['results'][0]['location'] + str(data['results'][0]['work_item_id'])}
        next_url = data['next']
        for _ in range(2):
            resp = self.client.get(next_url.replace('http://testserver', ''))
            page = resp.json()
            assert len(page['results']) == 1
            key = page['results'][0]['location'] + str(page['results'][0]['work_item_id'])
            assert key not in seen
            seen.add(key)
            next_url = page['next']
        assert next_url is None

    def test_category_filter(self):
        self.client.force_login(self.user)
        response = self.client.get(f'/api/location-progress/data/?work_ids={self.work.pk}&category=supply_installation')
        data = response.json()
        assert data['count'] == 1
        assert data['results'][0]['location'] == 'BRC'

    def test_location_search(self):
        self.client.force_login(self.user)
        response = self.client.get(f'/api/location-progress/data/?work_ids={self.work.pk}&location=asv')
        data = response.json()
        assert data['count'] == 1
        assert data['results'][0]['location'] == 'ASV-NRD'

    def test_location_type_section_vs_station(self):
        self.client.force_login(self.user)
        response = self.client.get(f'/api/location-progress/data/?work_ids={self.work.pk}')
        data = response.json()
        by_loc = {r['location']: r for r in data['results']}
        assert by_loc['ADI']['location_type'] == 'station'
        assert by_loc['ASV-NRD']['location_type'] == 'section'

    def test_stats(self):
        self.client.force_login(self.user)
        response = self.client.get(f'/api/location-progress/data/?work_ids={self.work.pk}')
        stats = response.json()['stats']
        assert stats['sections'] == 1   # ASV-NRD
        assert stats['stations'] == 2   # ADI, BRC
        assert stats['exCount'] == 2    # ADI, ASV-NRD (item_exec)
        assert stats['siCount'] == 1    # BRC (item_si)

    def test_privacy_non_owner_sees_only_own_entries(self):
        """consignee2 (self.other) isn't the assigned consignee for this work —
        should see cumulative totals but only their own entry in the detail list."""
        self.client.force_login(self.other)
        response = self.client.get(f'/api/location-progress/data/?work_ids={self.work.pk}')
        data = response.json()
        adi_row = next(r for r in data['results'] if r['location'] == 'ADI')
        assert adi_row['entries_count'] == 2          # cumulative total unaffected
        assert adi_row['visible_entries_count'] == 1   # but only their own entry shown
        assert len(adi_row['entries']) == 1
        assert adi_row['entries'][0]['quantity'] == 10.0

    def test_owner_sees_all_entries(self):
        self.client.force_login(self.user)
        response = self.client.get(f'/api/location-progress/data/?work_ids={self.work.pk}')
        data = response.json()
        adi_row = next(r for r in data['results'] if r['location'] == 'ADI')
        assert adi_row['visible_entries_count'] == 2
        assert len(adi_row['entries']) == 2

    def test_unauthenticated_rejected(self):
        response = self.client.get('/api/location-progress/data/')
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
