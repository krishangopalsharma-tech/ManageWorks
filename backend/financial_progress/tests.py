import pytest
from django.contrib.auth.models import User
from django.test import Client
from rest_framework import status
from users.models import UserProfile
from works.models import Work
from .models import BillRecord


@pytest.mark.django_db
class TestFinancialProgressBillPermissions:

    @pytest.fixture(autouse=True)
    def setup_data(self):
        self.client = Client()

        self.super_admin = User.objects.create_user(username='admin', password='password123')
        UserProfile.objects.create(user=self.super_admin, designation='Super Admin', is_approved=True, role='admin', is_super_admin=True)

        self.plain_admin = User.objects.create_user(username='admin2', password='password123')
        UserProfile.objects.create(user=self.plain_admin, designation='Admin', is_approved=True, role='admin')

        self.consignee1 = User.objects.create_user(username='consignee1', password='password123')
        UserProfile.objects.create(user=self.consignee1, designation='Consignee 1', is_approved=True, role='consignee')

        self.consignee2 = User.objects.create_user(username='consignee2', password='password123')
        UserProfile.objects.create(user=self.consignee2, designation='Consignee 2', is_approved=True, role='consignee')

        self.unassigned = User.objects.create_user(username='unassigned1', password='password123')
        UserProfile.objects.create(user=self.unassigned, designation='Unassigned', is_approved=True, role='consignee')

        self.work1 = Work.objects.create(loa_number='LOA-2026-001', contractor_name='Apex', hrms_id='consignee1')
        self.bill1 = BillRecord.objects.create(work=self.work1, bill_number='B-1')

    def test_super_admin_can_delete_any_bill(self):
        self.client.force_login(self.super_admin)
        response = self.client.delete(f'/api/financial-progress/bills/{self.bill1.pk}/')
        assert response.status_code == status.HTTP_200_OK
        assert not BillRecord.objects.filter(pk=self.bill1.pk).exists()

    def test_super_admin_can_edit_any_bill(self):
        self.client.force_login(self.super_admin)
        response = self.client.patch(
            f'/api/financial-progress/bills/{self.bill1.pk}/',
            {'bill_number': 'B-1-Updated'},
            content_type='application/json',
        )
        assert response.status_code == status.HTTP_200_OK
        self.bill1.refresh_from_db()
        assert self.bill1.bill_number == 'B-1-Updated'

    def test_plain_admin_cannot_delete_bill(self):
        self.client.force_login(self.plain_admin)
        response = self.client.delete(f'/api/financial-progress/bills/{self.bill1.pk}/')
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert BillRecord.objects.filter(pk=self.bill1.pk).exists()

    def test_plain_admin_cannot_edit_bill(self):
        self.client.force_login(self.plain_admin)
        response = self.client.patch(
            f'/api/financial-progress/bills/{self.bill1.pk}/',
            {'bill_number': 'Hacked'},
            content_type='application/json',
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_assigned_consignee_can_delete_own_loa_bill(self):
        self.client.force_login(self.consignee1)
        response = self.client.delete(f'/api/financial-progress/bills/{self.bill1.pk}/')
        assert response.status_code == status.HTTP_200_OK
        assert not BillRecord.objects.filter(pk=self.bill1.pk).exists()

    def test_assigned_consignee_can_edit_own_loa_bill(self):
        self.client.force_login(self.consignee1)
        response = self.client.patch(
            f'/api/financial-progress/bills/{self.bill1.pk}/',
            {'bill_number': 'B-1-Consignee-Edit'},
            content_type='application/json',
        )
        assert response.status_code == status.HTTP_200_OK
        self.bill1.refresh_from_db()
        assert self.bill1.bill_number == 'B-1-Consignee-Edit'

    def test_other_consignee_cannot_delete_bill(self):
        self.client.force_login(self.consignee2)
        response = self.client.delete(f'/api/financial-progress/bills/{self.bill1.pk}/')
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_unassigned_consignee_cannot_delete_bill(self):
        self.client.force_login(self.unassigned)
        response = self.client.delete(f'/api/financial-progress/bills/{self.bill1.pk}/')
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_unassigned_consignee_no_access_via_get(self):
        self.client.force_login(self.unassigned)
        response = self.client.get(f'/api/financial-progress/bills/{self.bill1.pk}/')
        assert response.status_code == status.HTTP_403_FORBIDDEN
