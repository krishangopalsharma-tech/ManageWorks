import pytest
from unittest.mock import patch
from django.contrib.auth.models import User
from django.test import Client
from rest_framework import status
from users.models import UserProfile
from works.models import Work

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
            is_super_admin=True,
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

        # Plain admin — role='admin' but NOT the super-admin username, NOT is_staff
        self.plain_admin = User.objects.create_user(username='admin2', password='password123', email='admin2@example.com')
        UserProfile.objects.create(
            user=self.plain_admin,
            designation='Regional Admin',
            is_approved=True,
            role='admin',
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

    def test_me_is_assigned_true_when_work_assigned(self):
        Work.objects.create(loa_number='LOA-ASSIGNED-1', contractor_name='Apex', hrms_id='consignee1')
        self.client.force_login(self.consignee)
        response = self.client.get('/api/auth/me/')
        assert response.json()['is_assigned'] is True

    def test_me_is_assigned_false_when_no_work_assigned(self):
        self.client.force_login(self.consignee)
        response = self.client.get('/api/auth/me/')
        assert response.json()['is_assigned'] is False

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

    # ── Plain Admin is NOT Super Admin: approve/reject/revoke/role-change are super-admin-only ──

    def test_plain_admin_cannot_approve(self):
        self.client.force_login(self.plain_admin)
        response = self.client.post(f'/api/auth/approve/{self.pending_user.pk}/')
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_plain_admin_cannot_reject(self):
        self.client.force_login(self.plain_admin)
        response = self.client.delete(f'/api/auth/reject/{self.pending_user.pk}/')
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_plain_admin_cannot_revoke(self):
        self.client.force_login(self.plain_admin)
        response = self.client.post(f'/api/auth/revoke/{self.consignee.pk}/')
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_plain_admin_cannot_update_role(self):
        self.client.force_login(self.plain_admin)
        response = self.client.patch(f'/api/auth/role/{self.consignee.pk}/', {
            'role': 'admin'
        }, content_type='application/json')
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_plain_admin_cannot_update_role_via_update_user_view(self):
        self.client.force_login(self.plain_admin)
        response = self.client.patch(f'/api/auth/update/{self.consignee.pk}/', {
            'role': 'admin'
        }, content_type='application/json')
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_plain_admin_can_still_view_users(self):
        self.client.force_login(self.plain_admin)
        assert self.client.get('/api/auth/pending/').status_code == status.HTTP_200_OK
        assert self.client.get('/api/auth/all/').status_code == status.HTTP_200_OK

    def test_plain_admin_cannot_edit_designation(self):
        """UpdateUserView is fully Super-Admin-only now — a plain Admin can view
        users but not write any field here, not even designation/email."""
        self.client.force_login(self.plain_admin)
        response = self.client.patch(f'/api/auth/update/{self.consignee.pk}/', {
            'designation': 'Updated Designation'
        }, content_type='application/json')
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_super_admin_can_edit_designation_and_email(self):
        self.client.force_login(self.admin)
        response = self.client.patch(f'/api/auth/update/{self.consignee.pk}/', {
            'designation': 'Updated Designation',
            'email': 'updated@example.com',
        }, content_type='application/json')
        assert response.status_code == status.HTTP_200_OK
        self.profile.refresh_from_db()
        self.consignee.refresh_from_db()
        assert self.profile.designation == 'Updated Designation'
        assert self.consignee.email == 'updated@example.com'

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


@pytest.mark.django_db
class TestAdminAutoConvertToConsignee:
    """Assigning a Work/LOA to an Admin auto-converts them to Consignee (one-way).
    Super Admin (username='admin') is never auto-converted. Reassigning away from
    an existing consignee must not change that consignee's role."""

    @pytest.fixture(autouse=True)
    def setup_data(self):
        self.client = Client()

        self.super_admin = User.objects.create_superuser(username='admin', password='password123')
        UserProfile.objects.create(user=self.super_admin, designation='Super Admin', is_approved=True, role='admin', is_super_admin=True)

        self.zero_loa_admin = User.objects.create_user(username='admin2', password='password123')
        self.zero_loa_admin_profile = UserProfile.objects.create(
            user=self.zero_loa_admin, designation='Regional Admin', is_approved=True, role='admin'
        )

        self.consignee = User.objects.create_user(username='consignee1', password='password123')
        self.consignee_profile = UserProfile.objects.create(
            user=self.consignee, designation='Consignee', is_approved=True, role='consignee'
        )

        self.work = Work.objects.create(loa_number='LOA-CONVERT-1', contractor_name='Apex')

    def test_assigning_work_converts_admin_to_consignee(self):
        self.client.force_login(self.super_admin)
        response = self.client.post('/api/auth/assign-work/', {
            'work_id': self.work.pk,
            'hrms_id': 'admin2',
        }, content_type='application/json')
        assert response.status_code == status.HTTP_200_OK
        self.zero_loa_admin_profile.refresh_from_db()
        assert self.zero_loa_admin_profile.role == 'consignee'

    def test_super_admin_never_auto_converted(self):
        self.client.force_login(self.super_admin)
        response = self.client.post('/api/auth/assign-work/', {
            'work_id': self.work.pk,
            'hrms_id': 'admin',
        }, content_type='application/json')
        assert response.status_code == status.HTTP_200_OK
        super_admin_profile = UserProfile.objects.get(user=self.super_admin)
        assert super_admin_profile.role == 'admin'

    def test_reassigning_away_does_not_change_old_consignees_role(self):
        self.work.hrms_id = 'consignee1'
        self.work.save(update_fields=['hrms_id'])
        self.consignee_profile.refresh_from_db()
        assert self.consignee_profile.role == 'consignee'

        self.client.force_login(self.super_admin)
        response = self.client.post('/api/auth/assign-work/', {
            'work_id': self.work.pk,
            'hrms_id': '',
        }, content_type='application/json')
        assert response.status_code == status.HTTP_200_OK
        self.consignee_profile.refresh_from_db()
        assert self.consignee_profile.role == 'consignee'

    def test_creating_work_with_admin_hrms_id_converts_immediately(self):
        Work.objects.create(loa_number='LOA-CONVERT-2', contractor_name='Builders', hrms_id='admin2')
        self.zero_loa_admin_profile.refresh_from_db()
        assert self.zero_loa_admin_profile.role == 'consignee'

    def test_assigning_work_to_existing_consignee_is_a_noop(self):
        self.client.force_login(self.super_admin)
        response = self.client.post('/api/auth/assign-work/', {
            'work_id': self.work.pk,
            'hrms_id': 'consignee1',
        }, content_type='application/json')
        assert response.status_code == status.HTTP_200_OK
        self.consignee_profile.refresh_from_db()
        assert self.consignee_profile.role == 'consignee'
