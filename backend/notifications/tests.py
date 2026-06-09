import pytest
from django.contrib.auth.models import User
from django.test import Client
from rest_framework import status
from works.models import Work, WorkItem, WorkItemEntry
from site_register.models import SiteRegisterThread
from notifications.models import Notification

@pytest.mark.django_db
class TestNotificationSignals:

    @pytest.fixture(autouse=True)
    def setup_users(self):
        self.admin = User.objects.create_superuser(username='admin', password='pass', email='admin@example.com')
        self.consignee = User.objects.create_user(username='consignee1', password='pass', email='c1@example.com')
        # Work order assigned to consignee1
        self.work = Work.objects.create(
            loa_number='LOA-2026-001',
            contractor_name='Apex Builders',
            hrms_id='consignee1'
        )

    def test_new_sr_notif_created(self):
        # Create SiteRegisterThread -> admin and consignee get notification
        thread = SiteRegisterThread.objects.create(
            work=self.work,
            initiated_by_role='rly_official',
            category='progress',
            initial_text='Starting base foundation.',
            created_by=self.admin,
            work_serial=1
        )
        
        # Check notifications created
        notifs = Notification.objects.filter(thread=thread)
        assert notifs.count() == 2
        
        admin_notif = notifs.filter(user=self.admin).first()
        consignee_notif = notifs.filter(user=self.consignee).first()
        
        assert admin_notif is not None
        assert admin_notif.notif_type == 'new_sr'
        assert 'LOA-2026-001' in admin_notif.body
        assert '0001' in admin_notif.title  # sr_number formatted
        
        assert consignee_notif is not None
        assert consignee_notif.notif_type == 'new_sr'
        
    def test_new_sr_no_hrms(self):
        # Work with no hrms_id -> only admin is notified
        work_no_consignee = Work.objects.create(
            loa_number='LOA-2026-002',
            contractor_name='Apex Builders'
        )
        thread = SiteRegisterThread.objects.create(
            work=work_no_consignee,
            initiated_by_role='rly_official',
            category='progress',
            initial_text='Unassigned work progress.',
            created_by=self.admin,
            work_serial=2
        )
        
        notifs = Notification.objects.filter(thread=thread)
        assert notifs.count() == 1
        assert notifs.filter(user=self.admin).exists()
        assert not notifs.filter(user=self.consignee).exists()

    def test_wi_entry_notifications(self):
        # Test supply category -> ss_entry
        item_supply = WorkItem.objects.create(
            work=self.work,
            serial_number='1',
            category='supply',
            item_desc='Copper Cable',
            qty=100
        )
        entry_supply = WorkItemEntry.objects.create(
            work_item=item_supply,
            entry_type='supply',
            quantity=50
        )
        
        notifs = Notification.objects.filter(notif_type='ss_entry')
        assert notifs.count() == 2  # Admin + Consignee
        assert 'Copper Cable' in notifs.first().body
        assert 'Qty: 50' in notifs.first().body

        # Test supply_installation category -> si_entry
        item_si = WorkItem.objects.create(
            work=self.work,
            serial_number='2',
            category='supply_installation',
            item_desc='Transformer Inst',
            qty=2
        )
        entry_si = WorkItemEntry.objects.create(
            work_item=item_si,
            entry_type='supply',
            quantity=1
        )
        assert Notification.objects.filter(notif_type='si_entry').count() == 2

        # Test execution category -> ee_entry
        item_exec = WorkItem.objects.create(
            work=self.work,
            serial_number='3',
            category='execution',
            item_desc='Trench Digging',
            qty=500
        )
        entry_exec = WorkItemEntry.objects.create(
            work_item=item_exec,
            entry_type='execution',
            quantity=200
        )
        assert Notification.objects.filter(notif_type='ee_entry').count() == 2

    def test_unknown_category_no_notif(self):
        item_none = WorkItem.objects.create(
            work=self.work,
            serial_number='4',
            category=None,
            qty=10
        )
        WorkItemEntry.objects.create(
            work_item=item_none,
            entry_type='supply',
            quantity=5
        )
        # Should not create any wi notifications
        assert Notification.objects.filter(notif_type__in=['ss_entry', 'si_entry', 'ee_entry']).count() == 0

    def test_loa_unassigned_notif(self):
        # Change Work hrms_id to another user -> old consignee gets loa_unassigned
        other_consignee = User.objects.create_user(username='consignee2', password='pass', email='c2@example.com')
        
        self.work.hrms_id = 'consignee2'
        self.work.save()
        
        notifs = Notification.objects.filter(user=self.consignee, notif_type='loa_unassigned')
        assert notifs.count() == 1
        assert 'LOA-2026-001' in notifs.first().title

    def test_loa_unassigned_new_work(self):
        # New work with hrms_id -> NO unassigned notification
        Work.objects.create(
            loa_number='LOA-2026-999',
            hrms_id='consignee1'
        )
        assert Notification.objects.filter(notif_type='loa_unassigned').count() == 0

    def test_loa_unassigned_same_hrms(self):
        # Saving unchanged hrms_id -> NO notification
        self.work.contractor_name = 'New Contractor'
        self.work.save()
        assert Notification.objects.filter(notif_type='loa_unassigned').count() == 0

    def test_loa_unassigned_user_not_found(self):
        # Work old hrms_id has no matching User -> no crash, no notif
        self.work.hrms_id = 'nonexistent'
        self.work.save()
        
        # Clear any notifications just in case
        Notification.objects.all().delete()
        
        # Now change it to 'consignee1'
        self.work.hrms_id = 'consignee1'
        self.work.save()
        
        assert Notification.objects.filter(notif_type='loa_unassigned').count() == 0

    def test_sr_thread_update_no_notif(self):
        # Update existing thread -> no new notifications
        thread = SiteRegisterThread.objects.create(
            work=self.work,
            initiated_by_role='rly_official',
            category='progress',
            initial_text='Original Text',
            created_by=self.admin
        )
        initial_count = Notification.objects.count()
        thread.status = 'replied'
        thread.save()
        assert Notification.objects.count() == initial_count


@pytest.mark.django_db
class TestNotificationAPI:

    @pytest.fixture(autouse=True)
    def setup_api(self):
        self.client = Client()
        self.user = User.objects.create_user(username='user1', password='pass')
        self.admin = User.objects.create_superuser(username='admin1', password='pass')
        self.work = Work.objects.create(loa_number='LOA-123', hrms_id='user1')
        
        # Create some notifications for user1
        self.notif1 = Notification.objects.create(
            user=self.user,
            notif_type='new_sr',
            title='SR-1',
            body='Test',
            is_read=False
        )
        self.notif2 = Notification.objects.create(
            user=self.user,
            notif_type='financial',
            title='MB-1',
            body='Test',
            is_read=False
        )
        # Notification for another user
        self.notif_other = Notification.objects.create(
            user=self.admin,
            notif_type='new_sr',
            title='SR-2',
            body='Test',
            is_read=False
        )

    def test_notif_list_unauthenticated(self):
        response = self.client.get('/api/notifications/')
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_notif_list_own_only(self):
        self.client.force_login(self.user)
        response = self.client.get('/api/notifications/')
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data['notifications']) == 2
        assert data['unread_count'] == 2
        # Verify serialize fields
        notif_ids = [n['id'] for n in data['notifications']]
        assert self.notif1.pk in notif_ids
        assert self.notif2.pk in notif_ids
        assert self.notif_other.pk not in notif_ids

    def test_notif_list_limit(self):
        self.client.force_login(self.user)
        # Create 70 notifications
        Notification.objects.all().delete()
        for i in range(75):
            Notification.objects.create(
                user=self.user,
                notif_type='ss_entry',
                title=f'Notif-{i}',
                is_read=False
            )
        response = self.client.get('/api/notifications/')
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data['notifications']) == 60  # capped at 60
        assert data['unread_count'] == 75       # actual unread count

    def test_notif_mark_read(self):
        self.client.force_login(self.user)
        response = self.client.post(f'/api/notifications/{self.notif1.pk}/read/')
        assert response.status_code == status.HTTP_200_OK
        self.notif1.refresh_from_db()
        assert self.notif1.is_read is True
        self.notif2.refresh_from_db()
        assert self.notif2.is_read is False

    def test_notif_mark_all_read(self):
        self.client.force_login(self.user)
        response = self.client.post('/api/notifications/')
        assert response.status_code == status.HTTP_200_OK
        self.notif1.refresh_from_db()
        self.notif2.refresh_from_db()
        assert self.notif1.is_read is True
        assert self.notif2.is_read is True
        # Other user's notif should remain unread
        self.notif_other.refresh_from_db()
        assert self.notif_other.is_read is False
