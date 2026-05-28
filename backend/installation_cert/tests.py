import pytest
from django.contrib.auth.models import User
from django.test import Client
from rest_framework import status
from works.models import Work, WorkItem, WorkItemEntry
from installation_cert.models import GeneratedCertificate
from installation_cert.views import _auto_cert_number, _work_fy
from users.models import UserProfile

@pytest.mark.django_db
class TestInstallationCertificate:

    @pytest.fixture(autouse=True)
    def setup_data(self):
        self.client = Client()
        self.user = User.objects.create_user(username='consignee1', password='password123')
        UserProfile.objects.create(user=self.user, designation='JE/Tele', pf_number='PF-01', is_approved=True, role='consignee')

        self.work = Work.objects.create(
            loa_number='LOA-2026-X',
            tender_number='Tele 02 of 25-26',
            date='2026-05-28',
            contractor_name='Apex',
            hrms_id='consignee1'
        )
        self.item = WorkItem.objects.create(
            work=self.work, serial_number='1.1', schedule='B', item_desc='Install cable',
            qty=100.0, unit='Metres', unit_rate_below=10.0, total_amount=1000.0,
            category='execution' # supply category is excluded, execution is included!
        )
        self.entry = WorkItemEntry.objects.create(
            work_item=self.item,
            entry_type='execution',
            quantity=10.0,
            submitted_by=self.user
        )

    def test_cert_generate(self):
        self.client.force_login(self.user)
        response = self.client.post('/api/installation-cert/generate/', {
            'loa_id': self.work.pk,
            'entry_ids': [self.entry.pk],
            'cert_number': 'TEST-CERT-001'
        }, content_type='application/json')
        assert response.status_code == status.HTTP_200_OK
        
        # Verify db record
        cert = GeneratedCertificate.objects.get(cert_number='TEST-CERT-001')
        assert cert.work == self.work
        assert cert.user == self.user
        assert cert.entry_ids == [self.entry.pk]

    def test_cert_auto_number(self):
        # seq = 1
        num1 = _auto_cert_number(self.work, cert_seq=1)
        # Sequence format: {prefix} {work_seq:02d} of {fy}/{cert_seq:03d}
        # tender_number starts with "Tele" -> prefix = "Tele". work_seq = 1. fy = 26-27 (since date is 2026-05-28, which is May 2026 -> FY 26-27)
        assert 'Tele' in num1
        assert '/001' in num1
        
        # seq = 2
        num2 = _auto_cert_number(self.work, cert_seq=2)
        assert '/002' in num2

    def test_cert_pdf_response(self):
        # First generate a certificate
        cert = GeneratedCertificate.objects.create(
            user=self.user,
            work=self.work,
            cert_number='TEST-CERT-002',
            entry_ids=[self.entry.pk],
            designation='JE/Tele'
        )
        
        self.client.force_login(self.user)
        response = self.client.get(f'/api/installation-cert/certificates/{cert.pk}/pdf/')
        # In a real system ReportLab compiles PDF and returns FileResponse (application/pdf)
        assert response.status_code == status.HTTP_200_OK
        assert response['Content-Type'] == 'application/pdf'
