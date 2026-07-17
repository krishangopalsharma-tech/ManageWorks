import pytest
from django.contrib.auth.models import User
from django.test import Client
from rest_framework import status
from users.models import UserProfile
from works.models import Work, WorkItem, WorkItemEntry


@pytest.mark.django_db
class TestWorkDetailsScoping:
    """Every authenticated user can list/search all LOAs (progress-view). Full
    entry-level detail is limited to Admin/Super Admin and the LOA's own assigned
    consignee; everyone else sees item data but only their own submitted entries."""

    @pytest.fixture(autouse=True)
    def setup_data(self):
        self.client = Client()

        self.admin = User.objects.create_superuser(username='admin', password='password123')
        UserProfile.objects.create(user=self.admin, designation='Admin', is_approved=True, role='admin')

        self.consignee1 = User.objects.create_user(username='consignee1', password='password123')
        UserProfile.objects.create(user=self.consignee1, designation='Consignee 1', is_approved=True, role='consignee')

        self.consignee2 = User.objects.create_user(username='consignee2', password='password123')
        UserProfile.objects.create(user=self.consignee2, designation='Consignee 2', is_approved=True, role='consignee')

        self.work1 = Work.objects.create(loa_number='LOA-WD-001', contractor_name='Apex', hrms_id='consignee1')
        self.item1 = WorkItem.objects.create(work=self.work1, schedule='A', serial_number='1', category='execution')

        WorkItemEntry.objects.create(
            work_item=self.item1, entry_type='execution', quantity=5,
            submitted_by=self.consignee1,
        )
        WorkItemEntry.objects.create(
            work_item=self.item1, entry_type='execution', quantity=3,
            submitted_by=self.consignee2,
        )

    def test_consignee_search_sees_all_loas(self):
        self.client.force_login(self.consignee2)
        response = self.client.get('/api/work-details/search/')
        assert response.status_code == status.HTTP_200_OK
        loa_numbers = [w['loa_number'] for w in response.json()]
        assert 'LOA-WD-001' in loa_numbers

    def test_unassigned_consignee_search_sees_all_loas_too(self):
        self.client.force_login(self.consignee2)
        response = self.client.get('/api/work-details/search/')
        assert response.status_code == status.HTTP_200_OK
        assert len(response.json()) >= 1

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
