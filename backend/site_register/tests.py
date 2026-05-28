import pytest
from datetime import timedelta
from freezegun import freeze_time
from django.contrib.auth.models import User
from django.test import Client
from django.utils import timezone
from rest_framework import status
from works.models import Work, WorkItem
from users.models import UserProfile
from site_register.models import (
    SiteRegisterThread, SiteRegisterMessage,
    TelegramLinkOTP, TelegramUserLink,
    SupervisorInvite, WorkContractorTelegram
)

@pytest.mark.django_db
class TestSiteRegister:

    @pytest.fixture(autouse=True)
    def setup_data(self):
        self.client = Client()
        
        # Create users
        self.admin = User.objects.create_superuser(username='admin', password='password123', email='admin@example.com')
        UserProfile.objects.create(
            user=self.admin,
            designation='Admin Designation',
            pf_number='PF-ADM001',
            is_approved=True,
            role='admin'
        )

        self.consignee1 = User.objects.create_user(username='consignee1', password='password123')
        UserProfile.objects.create(
            user=self.consignee1,
            designation='JE-1',
            pf_number='PF-CON1',
            is_approved=True,
            role='consignee'
        )

        self.consignee2 = User.objects.create_user(username='consignee2', password='password123')
        UserProfile.objects.create(
            user=self.consignee2,
            designation='JE-2',
            pf_number='PF-CON2',
            is_approved=True,
            role='consignee'
        )

        # Create works
        self.work1 = Work.objects.create(loa_number='LOA-2026-001', contractor_name='Apex', hrms_id='consignee1')
        self.work2 = Work.objects.create(loa_number='LOA-2026-002', contractor_name='Builders', hrms_id='consignee2')

    def test_sr_access_admin(self):
        self.client.force_login(self.admin)
        response = self.client.get('/api/site-register/')
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        work_ids = [w['work_id'] for w in data['works']]
        assert self.work1.pk in work_ids
        assert self.work2.pk in work_ids

    def test_sr_access_consignee_own_work(self):
        self.client.force_login(self.consignee1)
        response = self.client.get('/api/site-register/')
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        work_ids = [w['work_id'] for w in data['works']]
        assert self.work1.pk in work_ids
        assert self.work2.pk not in work_ids  # Should NOT see work2

    def test_sr_access_unauthenticated(self):
        response = self.client.get('/api/site-register/')
        assert response.status_code == status.HTTP_403_FORBIDDEN  # raises PermissionDenied in DRF -> 403

    def test_sr_number_format(self):
        thread = SiteRegisterThread.objects.create(
            work=self.work1,
            initiated_by_role='rly_official',
            category='progress',
            initial_text='Starting base.',
            created_by=self.consignee1,
            work_serial=5
        )
        # sr_number = digits from loa + work_serial formatted
        # LOA-2026-001 -> digits = 2026001. digits[-5:] = 26001. serial = 0005 -> 26001-0005
        assert thread.sr_number == '26001-0005'

    def test_loa_parties_list(self):
        self.client.force_login(self.admin)
        response = self.client.get('/api/site-register/parties/')
        assert response.status_code == status.HTTP_200_OK
        
        # Non-admin forbidden
        self.client.force_login(self.consignee1)
        response = self.client.get('/api/site-register/parties/')
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_supervisor_invite_create(self):
        self.client.force_login(self.admin)
        response = self.client.post('/api/site-register/supervisor-invite/', {
            'loa_ids': [self.work1.pk, self.work2.pk]
        }, content_type='application/json')
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert 'code' in data
        assert len(data['code']) == 6

        # Check DB entry
        invite = SupervisorInvite.objects.get(code=data['code'])
        assert invite.loa_ids == [self.work1.pk, self.work2.pk]
        assert invite.created_by == self.admin

    def test_supervisor_invite_expired(self):
        # Generate invite
        invite = SupervisorInvite.generate(
            loa_ids=[self.work1.pk],
            created_by=self.admin
        )
        assert invite.is_expired is False
        
        # Freeze past 5 minutes
        future_time = timezone.now() + timedelta(minutes=6)
        with freeze_time(future_time):
            assert invite.is_expired is True

    def test_telegram_otp_generate(self):
        self.client.force_login(self.consignee1)
        # Get first
        response = self.client.get('/api/site-register/telegram/otp/')
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data['linked'] is False
        assert data['otp'] is None
        
        # Post to generate
        response = self.client.post('/api/site-register/telegram/otp/')
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert 'otp' in data
        assert len(data['otp']['code']) == 6

    def test_telegram_otp_expired(self):
        otp = TelegramLinkOTP.generate_for(self.consignee1)
        assert otp.is_expired is False
        
        # Expires in 1 minute
        future_time = timezone.now() + timedelta(minutes=2)
        with freeze_time(future_time):
            assert otp.is_expired is True

    def test_telegram_unlink(self):
        # Create link
        tg_link = TelegramUserLink.objects.create(
            user=self.consignee1,
            telegram_user_id=12345,
            telegram_chat_id=67890,
            is_verified=True
        )
        self.client.force_login(self.consignee1)
        
        response = self.client.delete('/api/site-register/telegram/unlink/')
        assert response.status_code == status.HTTP_200_OK
        assert not TelegramUserLink.objects.filter(pk=tg_link.pk).exists()
