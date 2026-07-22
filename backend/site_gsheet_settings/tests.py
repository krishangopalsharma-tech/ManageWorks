import pytest
from django.contrib.auth.models import User
from django.test import Client
from rest_framework import status
from users.models import UserProfile
from .models import SiteGSheet


@pytest.mark.django_db
class TestSiteGSheetSettingsPermissions:

    @pytest.fixture(autouse=True)
    def setup_users(self):
        self.client = Client()

        self.super_admin = User.objects.create_user(username='admin', password='password123')
        UserProfile.objects.create(user=self.super_admin, designation='Super Admin', is_approved=True, role='admin', is_super_admin=True)

        self.plain_admin = User.objects.create_user(username='admin2', password='password123')
        UserProfile.objects.create(user=self.plain_admin, designation='Admin', is_approved=True, role='admin')

        self.consignee = User.objects.create_user(username='consignee1', password='password123')
        UserProfile.objects.create(user=self.consignee, designation='Consignee', is_approved=True, role='consignee')

        self.sheet = SiteGSheet.objects.create(name='Main Sheet', sheet_url='https://docs.google.com/spreadsheets/d/abc123/edit')

    def test_unauthenticated_forbidden(self):
        assert self.client.get('/api/settings/site-gsheet/sheets/').status_code == status.HTTP_403_FORBIDDEN
        assert self.client.post('/api/settings/site-gsheet/sheets/', {}).status_code == status.HTTP_403_FORBIDDEN
        assert self.client.get(f'/api/settings/site-gsheet/sheets/{self.sheet.pk}/').status_code == status.HTTP_403_FORBIDDEN
        assert self.client.put(f'/api/settings/site-gsheet/sheets/{self.sheet.pk}/', {}).status_code == status.HTTP_403_FORBIDDEN
        assert self.client.delete(f'/api/settings/site-gsheet/sheets/{self.sheet.pk}/').status_code == status.HTTP_403_FORBIDDEN

    def test_plain_admin_forbidden(self):
        self.client.force_login(self.plain_admin)
        assert self.client.get('/api/settings/site-gsheet/sheets/').status_code == status.HTTP_403_FORBIDDEN
        assert self.client.post('/api/settings/site-gsheet/sheets/', {}).status_code == status.HTTP_403_FORBIDDEN
        assert self.client.get(f'/api/settings/site-gsheet/sheets/{self.sheet.pk}/').status_code == status.HTTP_403_FORBIDDEN
        assert self.client.delete(f'/api/settings/site-gsheet/sheets/{self.sheet.pk}/').status_code == status.HTTP_403_FORBIDDEN

    def test_consignee_forbidden(self):
        self.client.force_login(self.consignee)
        assert self.client.get('/api/settings/site-gsheet/sheets/').status_code == status.HTTP_403_FORBIDDEN

    def test_super_admin_allowed(self):
        self.client.force_login(self.super_admin)
        assert self.client.get('/api/settings/site-gsheet/sheets/').status_code == status.HTTP_200_OK
        response = self.client.post(
            '/api/settings/site-gsheet/sheets/',
            {'name': 'New Sheet', 'sheet_url': 'https://docs.google.com/spreadsheets/d/xyz789/edit'},
            content_type='application/json',
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert self.client.get(f'/api/settings/site-gsheet/sheets/{self.sheet.pk}/').status_code == status.HTTP_200_OK
        response = self.client.put(
            f'/api/settings/site-gsheet/sheets/{self.sheet.pk}/',
            {'name': 'Renamed', 'sheet_url': self.sheet.sheet_url},
            content_type='application/json',
        )
        assert response.status_code == status.HTTP_200_OK
        assert self.client.delete(f'/api/settings/site-gsheet/sheets/{self.sheet.pk}/').status_code == status.HTTP_204_NO_CONTENT
