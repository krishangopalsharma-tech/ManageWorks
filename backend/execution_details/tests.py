import pytest
from django.contrib.auth.models import User
from django.test import Client
from rest_framework import status
from users.models import UserProfile
from works.models import Work, WorkItem, WorkItemEntry


@pytest.mark.django_db
class TestExecutionDetailsPermissions:
    """Execution Details: Admin/Super Admin view-only (no entry submission).
    Any authenticated consignee (assigned to this LOA, assigned elsewhere, or
    fully unassigned) can submit EE / SI-execution-portion entries on any LOA
    — matches the existing unrestricted execution-entry behavior."""

    @pytest.fixture(autouse=True)
    def setup_data(self):
        self.client = Client()

        self.admin = User.objects.create_superuser(username='admin', password='password123')
        UserProfile.objects.create(user=self.admin, designation='Admin', is_approved=True, role='admin', is_super_admin=True)

        self.plain_admin = User.objects.create_user(username='admin2', password='password123')
        UserProfile.objects.create(user=self.plain_admin, designation='Regional Admin', is_approved=True, role='admin')

        self.consignee1 = User.objects.create_user(username='consignee1', password='password123')
        UserProfile.objects.create(user=self.consignee1, designation='Consignee 1', is_approved=True, role='consignee')

        self.unassigned = User.objects.create_user(username='unassigned1', password='password123')
        UserProfile.objects.create(user=self.unassigned, designation='Unassigned', is_approved=True, role='consignee')

        self.work1 = Work.objects.create(loa_number='LOA-ED-001', contractor_name='Apex', hrms_id='consignee1')
        self.ee_item = WorkItem.objects.create(work=self.work1, schedule='B', serial_number='1', category=WorkItem.CATEGORY_EXECUTION)
        self.si_item = WorkItem.objects.create(work=self.work1, schedule='A', serial_number='2', category=WorkItem.CATEGORY_SUPPLY_INSTALLATION)
        self.ss_item = WorkItem.objects.create(work=self.work1, schedule='A', serial_number='3', category=WorkItem.CATEGORY_SUPPLY)

    def test_everyone_can_search_all_loas(self):
        for user in (self.admin, self.consignee1, self.unassigned):
            self.client.force_login(user)
            response = self.client.get('/api/execution-details/works/search/')
            assert response.status_code == status.HTTP_200_OK
            assert 'LOA-ED-001' in [w['loa_number'] for w in response.json()]

    def test_assigned_consignee_can_submit_execution_entry_on_own_loa(self):
        self.client.force_login(self.consignee1)
        response = self.client.post(
            f'/api/execution-details/items/{self.ee_item.pk}/entries/',
            {'quantity': 4, 'location': 'Km 12'},
            content_type='application/json',
        )
        assert response.status_code == status.HTTP_201_CREATED
        self.ee_item.refresh_from_db()
        assert self.ee_item.executed_quantity == 4

    def test_unassigned_consignee_can_submit_execution_entry_anywhere(self):
        self.client.force_login(self.unassigned)
        response = self.client.post(
            f'/api/execution-details/items/{self.ee_item.pk}/entries/',
            {'quantity': 2},
            content_type='application/json',
        )
        assert response.status_code == status.HTTP_201_CREATED

    def test_si_execution_portion_open_to_anyone(self):
        self.client.force_login(self.unassigned)
        response = self.client.post(
            f'/api/execution-details/items/{self.si_item.pk}/entries/',
            {'quantity': 1},
            content_type='application/json',
        )
        assert response.status_code == status.HTTP_201_CREATED

    def test_admin_cannot_submit_execution_entry(self):
        """Admin is view-only on Execution Details, per spec."""
        self.client.force_login(self.admin)
        response = self.client.post(
            f'/api/execution-details/items/{self.ee_item.pk}/entries/',
            {'quantity': 4},
            content_type='application/json',
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_supply_only_item_rejects_execution_entry(self):
        self.client.force_login(self.consignee1)
        response = self.client.post(
            f'/api/execution-details/items/{self.ss_item.pk}/entries/',
            {'quantity': 4},
            content_type='application/json',
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_submitter_can_edit_own_entry(self):
        self.client.force_login(self.consignee1)
        create_resp = self.client.post(
            f'/api/execution-details/items/{self.ee_item.pk}/entries/',
            {'quantity': 4},
            content_type='application/json',
        )
        entry_id = create_resp.json()['id']
        response = self.client.patch(
            f'/api/execution-details/entries/{entry_id}/',
            {'quantity': 7},
            content_type='application/json',
        )
        assert response.status_code == status.HTTP_200_OK
        self.ee_item.refresh_from_db()
        assert self.ee_item.executed_quantity == 7

    def test_admin_cannot_edit_existing_execution_entry(self):
        """Admin is fully view-only on Execution Details — no create, no edit."""
        entry = WorkItemEntry.objects.create(
            work_item=self.ee_item, entry_type='execution', quantity=4, submitted_by=self.consignee1,
        )
        self.client.force_login(self.admin)
        response = self.client.patch(
            f'/api/execution-details/entries/{entry.pk}/',
            {'quantity': 9},
            content_type='application/json',
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_non_submitter_cannot_edit_others_entry(self):
        entry = WorkItemEntry.objects.create(
            work_item=self.ee_item, entry_type='execution', quantity=4, submitted_by=self.consignee1,
        )
        self.client.force_login(self.unassigned)
        response = self.client.patch(
            f'/api/execution-details/entries/{entry.pk}/',
            {'quantity': 9},
            content_type='application/json',
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_super_admin_can_delete_entry_on_any_loa(self):
        entry = WorkItemEntry.objects.create(
            work_item=self.ee_item, entry_type='execution', quantity=4, submitted_by=self.consignee1,
        )
        self.client.force_login(self.admin)
        response = self.client.delete(f'/api/execution-details/entries/{entry.pk}/')
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not WorkItemEntry.objects.filter(pk=entry.pk).exists()
        self.ee_item.refresh_from_db()
        assert self.ee_item.executed_quantity == 0

    def test_assigned_consignee_can_delete_entry_on_own_loa(self):
        """Even an entry submitted by someone else on their own LOA — assigned
        consignee can correct a colleague's mistake, same as Supply Details."""
        entry = WorkItemEntry.objects.create(
            work_item=self.ee_item, entry_type='execution', quantity=4, submitted_by=self.unassigned,
        )
        self.client.force_login(self.consignee1)
        response = self.client.delete(f'/api/execution-details/entries/{entry.pk}/')
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not WorkItemEntry.objects.filter(pk=entry.pk).exists()

    def test_plain_admin_cannot_delete_entry(self):
        entry = WorkItemEntry.objects.create(
            work_item=self.ee_item, entry_type='execution', quantity=4, submitted_by=self.consignee1,
        )
        self.client.force_login(self.plain_admin)
        response = self.client.delete(f'/api/execution-details/entries/{entry.pk}/')
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert WorkItemEntry.objects.filter(pk=entry.pk).exists()

    def test_unassigned_consignee_cannot_delete_entry(self):
        entry = WorkItemEntry.objects.create(
            work_item=self.ee_item, entry_type='execution', quantity=4, submitted_by=self.consignee1,
        )
        self.client.force_login(self.unassigned)
        response = self.client.delete(f'/api/execution-details/entries/{entry.pk}/')
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert WorkItemEntry.objects.filter(pk=entry.pk).exists()
