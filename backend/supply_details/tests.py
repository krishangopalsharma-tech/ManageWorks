import pytest
from django.contrib.auth.models import User
from django.test import Client
from rest_framework import status
from users.models import UserProfile
from works.models import Work, WorkItem, WorkItemEntry


@pytest.mark.django_db
class TestSupplyDetailsPermissions:
    """Supply Details: Admin/Super Admin view-only (no entry submission).
    Assigned consignee gets full SS + SI-supply-portion rights on their own LOA
    only. Everyone else (other consignees, unassigned) gets no access."""

    @pytest.fixture(autouse=True)
    def setup_data(self):
        self.client = Client()

        self.admin = User.objects.create_superuser(username='admin', password='password123')
        UserProfile.objects.create(user=self.admin, designation='Admin', is_approved=True, role='admin')

        self.consignee1 = User.objects.create_user(username='consignee1', password='password123')
        UserProfile.objects.create(user=self.consignee1, designation='Consignee 1', is_approved=True, role='consignee')

        self.consignee2 = User.objects.create_user(username='consignee2', password='password123')
        UserProfile.objects.create(user=self.consignee2, designation='Consignee 2', is_approved=True, role='consignee')

        self.work1 = Work.objects.create(loa_number='LOA-SD-001', contractor_name='Apex', hrms_id='consignee1')
        self.ss_item = WorkItem.objects.create(work=self.work1, schedule='A', serial_number='1', category=WorkItem.CATEGORY_SUPPLY)
        self.si_item = WorkItem.objects.create(work=self.work1, schedule='A', serial_number='2', category=WorkItem.CATEGORY_SUPPLY_INSTALLATION)
        self.ee_item = WorkItem.objects.create(work=self.work1, schedule='B', serial_number='1', category=WorkItem.CATEGORY_EXECUTION)

    def test_admin_can_search_all_loas(self):
        self.client.force_login(self.admin)
        response = self.client.get('/api/supply-details/works/search/')
        assert response.status_code == status.HTTP_200_OK
        assert 'LOA-SD-001' in [w['loa_number'] for w in response.json()]

    def test_assigned_consignee_sees_own_loa_in_search(self):
        self.client.force_login(self.consignee1)
        response = self.client.get('/api/supply-details/works/search/')
        assert response.status_code == status.HTTP_200_OK
        assert 'LOA-SD-001' in [w['loa_number'] for w in response.json()]

    def test_other_consignee_does_not_see_non_owned_loa_in_search(self):
        self.client.force_login(self.consignee2)
        response = self.client.get('/api/supply-details/works/search/')
        assert response.status_code == status.HTTP_200_OK
        assert 'LOA-SD-001' not in [w['loa_number'] for w in response.json()]

    def test_other_consignee_cannot_retrieve_non_owned_loa(self):
        self.client.force_login(self.consignee2)
        response = self.client.get(f'/api/supply-details/works/{self.work1.pk}/detail/')
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_other_consignee_cannot_read_entries_on_non_owned_item(self):
        self.client.force_login(self.consignee2)
        response = self.client.get(f'/api/supply-details/items/{self.ss_item.pk}/entries/')
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_admin_can_retrieve_any_loa_and_read_entries(self):
        self.client.force_login(self.admin)
        response = self.client.get(f'/api/supply-details/works/{self.work1.pk}/detail/')
        assert response.status_code == status.HTTP_200_OK
        response = self.client.get(f'/api/supply-details/items/{self.ss_item.pk}/entries/')
        assert response.status_code == status.HTTP_200_OK

    def test_assigned_consignee_can_submit_ss_entry(self):
        self.client.force_login(self.consignee1)
        response = self.client.post(
            f'/api/supply-details/items/{self.ss_item.pk}/entries/',
            {'quantity': 5, 'challan_no': 'CH-1'},
            content_type='application/json',
        )
        assert response.status_code == status.HTTP_201_CREATED
        self.ss_item.refresh_from_db()
        assert self.ss_item.supplied_quantity == 5

    def test_assigned_consignee_can_submit_si_supply_portion(self):
        self.client.force_login(self.consignee1)
        response = self.client.post(
            f'/api/supply-details/items/{self.si_item.pk}/entries/',
            {'quantity': 3},
            content_type='application/json',
        )
        assert response.status_code == status.HTTP_201_CREATED

    def test_other_consignee_cannot_submit_supply_entry(self):
        self.client.force_login(self.consignee2)
        response = self.client.post(
            f'/api/supply-details/items/{self.ss_item.pk}/entries/',
            {'quantity': 5},
            content_type='application/json',
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_admin_cannot_submit_supply_entry(self):
        """Admin is view-only on Supply Details, per spec."""
        self.client.force_login(self.admin)
        response = self.client.post(
            f'/api/supply-details/items/{self.ss_item.pk}/entries/',
            {'quantity': 5},
            content_type='application/json',
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_execution_only_item_rejects_supply_entry(self):
        self.client.force_login(self.consignee1)
        response = self.client.post(
            f'/api/supply-details/items/{self.ee_item.pk}/entries/',
            {'quantity': 5},
            content_type='application/json',
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_duplicate_receive_note_rejected(self):
        self.client.force_login(self.consignee1)
        self.client.post(
            f'/api/supply-details/items/{self.ss_item.pk}/entries/',
            {'quantity': 5, 'receive_note_no': 'RN-1'},
            content_type='application/json',
        )
        response = self.client.post(
            f'/api/supply-details/items/{self.ss_item.pk}/entries/',
            {'quantity': 2, 'receive_note_no': 'RN-1'},
            content_type='application/json',
        )
        assert response.status_code == status.HTTP_409_CONFLICT

    def test_submitter_can_edit_own_entry(self):
        self.client.force_login(self.consignee1)
        create_resp = self.client.post(
            f'/api/supply-details/items/{self.ss_item.pk}/entries/',
            {'quantity': 5},
            content_type='application/json',
        )
        entry_id = create_resp.json()['id']
        response = self.client.patch(
            f'/api/supply-details/entries/{entry_id}/',
            {'quantity': 8},
            content_type='application/json',
        )
        assert response.status_code == status.HTTP_200_OK
        self.ss_item.refresh_from_db()
        assert self.ss_item.supplied_quantity == 8

    def test_admin_cannot_edit_existing_supply_entry(self):
        """Admin is fully view-only on Supply Details — no create, no edit."""
        entry = WorkItemEntry.objects.create(
            work_item=self.ss_item, entry_type='supply', quantity=5, submitted_by=self.consignee1,
        )
        self.client.force_login(self.admin)
        response = self.client.patch(
            f'/api/supply-details/entries/{entry.pk}/',
            {'quantity': 9},
            content_type='application/json',
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_edit_blocked_after_reassignment(self):
        entry = WorkItemEntry.objects.create(
            work_item=self.ss_item, entry_type='supply', quantity=5, submitted_by=self.consignee1,
        )
        self.work1.hrms_id = 'consignee2'
        self.work1.save(update_fields=['hrms_id'])

        self.client.force_login(self.consignee1)
        response = self.client.patch(
            f'/api/supply-details/entries/{entry.pk}/',
            {'quantity': 9},
            content_type='application/json',
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN
