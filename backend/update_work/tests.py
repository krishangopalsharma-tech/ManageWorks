import pytest
from django.contrib.auth.models import User
from django.test import Client
from rest_framework import status
from users.models import UserProfile
from works.models import Work


@pytest.mark.django_db
class TestUpdateWorkModifyPermission:
    """Update Work metadata edit: Admin/Super Admin can edit any LOA, assigned
    consignee can edit only their own LOA, unassigned consignee gets no access."""

    @pytest.fixture(autouse=True)
    def setup_data(self):
        self.client = Client()

        self.admin = User.objects.create_superuser(username='admin', password='password123')
        UserProfile.objects.create(user=self.admin, designation='Admin', is_approved=True, role='admin')

        self.consignee1 = User.objects.create_user(username='consignee1', password='password123')
        UserProfile.objects.create(user=self.consignee1, designation='Consignee 1', is_approved=True, role='consignee')

        self.consignee2 = User.objects.create_user(username='consignee2', password='password123')
        UserProfile.objects.create(user=self.consignee2, designation='Consignee 2', is_approved=True, role='consignee')

        self.work1 = Work.objects.create(loa_number='LOA-UW-001', contractor_name='Apex', hrms_id='consignee1')

    def test_admin_can_edit_any_work(self):
        self.client.force_login(self.admin)
        response = self.client.patch(
            f'/api/update-work/works/{self.work1.pk}/',
            {'name_of_work': 'Edited by admin'},
            content_type='application/json',
        )
        assert response.status_code == status.HTTP_200_OK
        self.work1.refresh_from_db()
        assert self.work1.name_of_work == 'Edited by admin'

    def test_assigned_consignee_can_edit_own_work(self):
        self.client.force_login(self.consignee1)
        response = self.client.patch(
            f'/api/update-work/works/{self.work1.pk}/',
            {'name_of_work': 'Edited by owner'},
            content_type='application/json',
        )
        assert response.status_code == status.HTTP_200_OK
        self.work1.refresh_from_db()
        assert self.work1.name_of_work == 'Edited by owner'

    def test_other_consignee_cannot_edit_non_owned_work(self):
        self.client.force_login(self.consignee2)
        response = self.client.patch(
            f'/api/update-work/works/{self.work1.pk}/',
            {'name_of_work': 'Hacked'},
            content_type='application/json',
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_unassigned_consignee_cannot_edit_unowned_work(self):
        unassigned = User.objects.create_user(username='unassigned1', password='password123')
        UserProfile.objects.create(user=unassigned, designation='Unassigned', is_approved=True, role='consignee')
        self.client.force_login(unassigned)
        response = self.client.patch(
            f'/api/update-work/works/{self.work1.pk}/',
            {'name_of_work': 'Hacked'},
            content_type='application/json',
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN
