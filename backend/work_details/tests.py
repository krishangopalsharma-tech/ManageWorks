import pytest
from django.contrib.auth.models import User
from django.test import Client
from rest_framework import status
from users.models import UserProfile
from works.models import Work, WorkItem, WorkItemEntry


@pytest.mark.django_db
class TestWorkDetailsScoping:
    """Every authenticated user can list/search all LOAs. Full entry-level detail
    and contract/billing fields are limited to Admin/Super Admin and the LOA's own
    assigned consignee; everyone else sees item/progress data (including rates,
    needed for progress-percentage math) but only their own submitted entries, and
    no contract-identity/billing fields.

    The frontend's Work Details page renders its per-LOA detail view straight from
    the /search/ response (it never calls the single-work retrieve endpoint), so
    these rules are tested against /search/ — that's the real, only path a browser
    hits."""

    @pytest.fixture(autouse=True)
    def setup_data(self):
        self.client = Client()

        self.admin = User.objects.create_superuser(username='admin', password='password123')
        UserProfile.objects.create(user=self.admin, designation='Admin', is_approved=True, role='admin')

        self.consignee1 = User.objects.create_user(username='consignee1', password='password123')
        UserProfile.objects.create(user=self.consignee1, designation='Consignee 1', is_approved=True, role='consignee')

        self.consignee2 = User.objects.create_user(username='consignee2', password='password123')
        UserProfile.objects.create(user=self.consignee2, designation='Consignee 2', is_approved=True, role='consignee')

        self.work1 = Work.objects.create(
            loa_number='LOA-WD-001', contractor_name='Apex', hrms_id='consignee1',
            contract_agreement='CA-9999', contractor_address='123 Depot Road',
        )
        self.item1 = WorkItem.objects.create(
            work=self.work1, schedule='A', serial_number='1', category='execution',
            unit_rate_rs=500, total_amount=2500,
        )

        WorkItemEntry.objects.create(
            work_item=self.item1, entry_type='execution', quantity=5,
            submitted_by=self.consignee1,
        )
        WorkItemEntry.objects.create(
            work_item=self.item1, entry_type='execution', quantity=3,
            submitted_by=self.consignee2,
        )

    def _row(self, response):
        return next(w for w in response.json() if w['loa_number'] == 'LOA-WD-001')

    def test_unassigned_consignee_search_sees_all_loas_too(self):
        self.client.force_login(self.consignee2)
        response = self.client.get('/api/work-details/search/')
        assert response.status_code == status.HTTP_200_OK
        assert len(response.json()) >= 1

    def test_admin_sees_full_detail_via_search(self):
        self.client.force_login(self.admin)
        row = self._row(self.client.get('/api/work-details/search/'))
        assert row['contract_agreement'] == 'CA-9999'
        assert row['items'][0]['unit_rate_rs'] == 500
        assert len(row['items'][0]['entries']) == 2

    def test_owner_consignee_sees_full_detail_via_search(self):
        """consignee1 is this LOA's assigned consignee (hrms_id='consignee1') —
        should see everything, since this is the only view the frontend uses."""
        self.client.force_login(self.consignee1)
        row = self._row(self.client.get('/api/work-details/search/'))
        assert row['contract_agreement'] == 'CA-9999'
        assert row['items'][0]['unit_rate_rs'] == 500
        assert len(row['items'][0]['entries']) == 2

    def test_non_owner_consignee_gets_progress_view_only_via_search(self):
        """consignee2 is NOT assigned to this LOA — no contract/billing fields,
        only their own submitted entries. Rates/qty stay visible (progress math)."""
        self.client.force_login(self.consignee2)
        row = self._row(self.client.get('/api/work-details/search/'))
        assert 'contract_agreement' not in row
        assert 'contractor_address' not in row
        assert 'bill_billing' not in row
        assert row['items'][0]['unit_rate_rs'] == 500
        entries = row['items'][0]['entries']
        assert len(entries) == 1
        assert entries[0]['submitted_by'] == self.consignee2.id

    def test_assigned_consignee_sees_all_entries_on_own_loa(self):
        self.client.force_login(self.consignee1)
        response = self.client.get(f'/api/work-details/{self.work1.pk}/')
        assert response.status_code == status.HTTP_200_OK
        entries = response.json()['items'][0]['entries']
        assert len(entries) == 2

    def test_other_consignee_sees_only_own_entries_on_non_owned_loa(self):
        self.client.force_login(self.consignee2)
        response = self.client.get(f'/api/work-details/{self.work1.pk}/')
        assert response.status_code == status.HTTP_200_OK
        entries = response.json()['items'][0]['entries']
        assert len(entries) == 1
        assert entries[0]['submitted_by'] == self.consignee2.id

    def test_other_consignee_does_not_see_financial_fields_on_non_owned_loa(self):
        self.client.force_login(self.consignee2)
        response = self.client.get(f'/api/work-details/{self.work1.pk}/')
        data = response.json()
        assert 'contract_agreement' not in data
        assert 'contractor_address' not in data
        assert 'bill_billing' not in data

    def test_assigned_consignee_sees_financial_fields_on_own_loa(self):
        self.client.force_login(self.consignee1)
        response = self.client.get(f'/api/work-details/{self.work1.pk}/')
        data = response.json()
        assert data['contract_agreement'] == 'CA-9999'
        assert data['items'][0]['unit_rate_rs'] == 500

    def test_admin_sees_all_entries_everywhere(self):
        self.client.force_login(self.admin)
        response = self.client.get(f'/api/work-details/{self.work1.pk}/')
        assert response.status_code == status.HTTP_200_OK
        entries = response.json()['items'][0]['entries']
        assert len(entries) == 2

    def test_unauthenticated_rejected(self):
        response = self.client.get('/api/work-details/search/')
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        response = self.client.get(f'/api/work-details/{self.work1.pk}/')
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
