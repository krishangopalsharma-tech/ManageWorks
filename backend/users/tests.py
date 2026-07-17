import pytest
from unittest.mock import patch
from django.contrib.auth.models import User
from django.test import Client
from rest_framework import status
from users.models import UserProfile

@pytest.mark.django_db
class TestUsersAuthAndRBAC:

    @pytest.fixture(autouse=True)
    def setup_users(self):
        self.client = Client()
        # Admin user
        self.admin = User.objects.create_superuser(username='admin', password='password123', email='admin@example.com')
        UserProfile.objects.create(
            user=self.admin,
            designation='Admin Officer',
            is_approved=True,
            role='admin',
            plain_password='password123'
        )

        # Consignee user (approved)
        self.consignee = User.objects.create_user(username='consignee1', password='password123', email='c1@example.com')
        self.profile = UserProfile.objects.create(
            user=self.consignee,
            designation='Consignee Grade 1',
            is_approved=True,
            role='consignee',
            plain_password='password123'
        )

        # Unapproved user
        self.pending_user = User.objects.create_user(username='pending1', password='password123', email='pending@example.com')
        self.pending_profile = UserProfile.objects.create(
            user=self.pending_user,
            designation='Assistant Consignee',
            is_approved=False,
            role='consignee',
            plain_password='password123'
        )

    def test_login_valid(self):
        response = self.client.post('/api/auth/login/', {
            'hrms_id': 'consignee1',
            'password': 'password123'
        }, content_type='application/json')
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data['hrms_id'] == 'consignee1'
        assert data['role'] == 'consignee'
        assert data['is_approved'] is True

    def test_login_wrong_password(self):
        response = self.client.post('/api/auth/login/', {
            'hrms_id': 'consignee1',
            'password': 'wrongpassword'
        }, content_type='application/json')
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_login_inactive_user(self):
        # Pending user tries to login -> 403 Forbidden
        response = self.client.post('/api/auth/login/', {
            'hrms_id': 'pending1',
            'password': 'password123'
        }, content_type='application/json')
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert 'pending admin approval' in response.json()['error']

    def test_logout(self):
        self.client.force_login(self.consignee)
        response = self.client.post('/api/auth/logout/')
        assert response.status_code == status.HTTP_200_OK
        # me should now return unauthenticated
        response_me = self.client.get('/api/auth/me/')
        assert response_me.status_code == status.HTTP_401_UNAUTHORIZED

    def test_register(self):
        response = self.client.post('/api/auth/register/', {
            'name': 'New User',
            'designation': 'Junior Engineer',
            'hrms_id': 'newuser123',
            'password': 'password123',
            'email': 'new@example.com'
        }, content_type='application/json')
        assert response.status_code == status.HTTP_201_CREATED
        
        # Verify user and profile created with pending status
        user = User.objects.get(username='newuser123')
        assert user.first_name == 'New User'
        assert user.email == 'new@example.com'
        
        profile = user.profile
        assert profile.designation == 'Junior Engineer'
        assert profile.is_approved is False
        assert profile.role == 'consignee'

    def test_register_missing_fields(self):
        response = self.client.post('/api/auth/register/', {
            'name': 'New User',
            'hrms_id': 'newuser123'
        }, content_type='application/json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_register_already_exists(self):
        response = self.client.post('/api/auth/register/', {
            'name': 'Duplicate',
            'designation': 'Eng',
            'hrms_id': 'consignee1',
            'password': 'password',
            'email': 'dup@example.com'
        }, content_type='application/json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_me_unauthenticated(self):
        response = self.client.get('/api/auth/me/')
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert response.json()['authenticated'] is False

    def test_me_authenticated(self):
        self.client.force_login(self.consignee)
        response = self.client.get('/api/auth/me/')
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data['authenticated'] is True
        assert data['hrms_id'] == 'consignee1'
        assert data['role'] == 'consignee'

    def test_approve_user_admin_only(self):
        self.client.force_login(self.consignee)
        response = self.client.post(f'/api/auth/approve/{self.pending_user.pk}/')
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_approve_user(self):
        self.client.force_login(self.admin)
        response = self.client.post(f'/api/auth/approve/{self.pending_user.pk}/')
        assert response.status_code == status.HTTP_200_OK
        self.pending_profile.refresh_from_db()
        assert self.pending_profile.is_approved is True

    def test_reject_user_admin_only(self):
        self.client.force_login(self.consignee)
        response = self.client.delete(f'/api/auth/reject/{self.pending_user.pk}/')
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_reject_user(self):
        self.client.force_login(self.admin)
        pk = self.pending_user.pk
        response = self.client.delete(f'/api/auth/reject/{pk}/')
        assert response.status_code == status.HTTP_200_OK
        assert not User.objects.filter(pk=pk).exists()

    def test_update_role(self):
        self.client.force_login(self.admin)
        response = self.client.patch(f'/api/auth/role/{self.consignee.pk}/', {
            'role': 'sse'
        }, content_type='application/json')
        assert response.status_code == status.HTTP_200_OK
        self.profile.refresh_from_db()
        assert self.profile.role == 'sse'

    def test_update_role_invalid(self):
        self.client.force_login(self.admin)
        response = self.client.patch(f'/api/auth/role/{self.consignee.pk}/', {
            'role': 'invalid_role'
        }, content_type='application/json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_revoke_user(self):
        self.client.force_login(self.admin)
        response = self.client.post(f'/api/auth/revoke/{self.consignee.pk}/')
        assert response.status_code == status.HTTP_200_OK
        self.profile.refresh_from_db()
        assert self.profile.is_approved is False

    @patch('users.views.send_password_email')
    def test_forgot_password_unknown_hrms(self, mock_send_email):
        response = self.client.post('/api/auth/forgot-password/', {
            'hrms_id': 'nonexistent'
        }, content_type='application/json')
        # Returns 200 with generic message for privacy
        assert response.status_code == status.HTTP_200_OK
        assert 'If that User ID exists' in response.json()['message']
        mock_send_email.assert_not_called()

    @patch('users.views.send_password_email')
    def test_forgot_password_valid(self, mock_send_email):
        response = self.client.post('/api/auth/forgot-password/', {
            'hrms_id': 'consignee1'
        }, content_type='application/json')
        assert response.status_code == status.HTTP_200_OK
        assert 'If that User ID exists' in response.json()['message']
        mock_send_email.assert_called_once_with(
            to_email='c1@example.com',
            user_name='consignee1',
            hrms_id='consignee1',
            plain_password='password123'
        )
