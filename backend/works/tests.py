import pytest
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from works.models import Work, WorkItem, WorkItemEntry, WorkExtension

@pytest.mark.django_db
class TestWorksModels:

    def test_work_create(self):
        work = Work.objects.create(
            loa_number='LOA-2026-X',
            tender_number='TENDER-X',
            date='2026-05-28',
            contract_agreement='AGREEMENT-X',
            name_of_work='Testing Work Model',
            contractor_name='Contractor X',
            contractor_address='123 Test St',
            date_of_completion='2026-12-31',
            consignee='Consignee X',
            hrms_id='consignee_hrms'
        )
        assert work.id is not None
        assert work.loa_number == 'LOA-2026-X'
        assert work.tender_number == 'TENDER-X'
        assert work.date == '2026-05-28'
        assert work.contract_agreement == 'AGREEMENT-X'
        assert work.name_of_work == 'Testing Work Model'
        assert work.contractor_name == 'Contractor X'
        assert work.contractor_address == '123 Test St'
        assert work.date_of_completion == '2026-12-31'
        assert work.consignee == 'Consignee X'
        assert work.hrms_id == 'consignee_hrms'

    def test_work_str(self):
        work = Work.objects.create(
            loa_number='LOA-2026-X',
            contractor_name='Contractor X'
        )
        assert str(work) == 'LOA-2026-X - Contractor X'

    def test_work_str_empty(self):
        work = Work.objects.create(
            contractor_name='Contractor X'
        )
        assert str(work) == 'Unknown Work - Contractor X'

    def test_work_item_cascade(self):
        work = Work.objects.create(loa_number='LOA-1', contractor_name='C1')
        item1 = WorkItem.objects.create(
            work=work,
            serial_number='1.1',
            category='supply',
            item_desc='Item 1',
            qty=10
        )
        item2 = WorkItem.objects.create(
            work=work,
            serial_number='1.2',
            category='execution',
            item_desc='Item 2',
            qty=20
        )
        
        assert WorkItem.objects.filter(work=work).count() == 2
        work.delete()
        # Item should be cascaded and deleted
        assert WorkItem.objects.filter(pk=item1.pk).count() == 0
        assert WorkItem.objects.filter(pk=item2.pk).count() == 0

    def test_work_extension(self):
        work = Work.objects.create(loa_number='LOA-1', contractor_name='C1')
        ext1 = WorkExtension.objects.create(work=work, extension_date='2026-06-30')
        ext2 = WorkExtension.objects.create(work=work, extension_date='2026-07-31')
        ext3 = WorkExtension.objects.create(work=work, extension_date='2026-08-31')
        
        # ordering by created_at
        extensions = list(work.extensions.all())
        assert extensions == [ext1, ext2, ext3]
        assert str(ext1) == f'Extension for {work.id}: 2026-06-30'

    def test_hrms_id_nullable(self):
        work = Work.objects.create(loa_number='LOA-2', hrms_id=None)
        assert work.hrms_id is None

    def test_work_item_entry_supply_type(self):
        work = Work.objects.create(loa_number='LOA-1', contractor_name='C1')
        item = WorkItem.objects.create(
            work=work,
            serial_number='1.1',
            category='supply',
            item_desc='Item 1',
            qty=10
        )
        # Verify valid entry
        entry = WorkItemEntry.objects.create(
            work_item=item,
            entry_type='supply',
            quantity=5
        )
        assert entry.entry_type == 'supply'
        assert entry.quantity == 5

    def test_work_item_entry_execution_location(self):
        work = Work.objects.create(loa_number='LOA-1', contractor_name='C1')
        item = WorkItem.objects.create(
            work=work,
            serial_number='1.2',
            category='execution',
            qty=100
        )
        entry = WorkItemEntry.objects.create(
            work_item=item,
            entry_type='execution',
            quantity=20,
            location='KM 124 to KM 125',
            remarks='Successfully laid cables.'
        )
        assert entry.location == 'KM 124 to KM 125'
        assert entry.remarks == 'Successfully laid cables.'

    def test_electrical_parameters_json(self):
        work = Work.objects.create(loa_number='LOA-1', contractor_name='C1')
        item = WorkItem.objects.create(work=work, serial_number='1.1', category='supply', qty=10)
        
        params = [
            {'param': 'Voltage', 'limit': '230V', 'result': '228V'},
            {'param': 'Current', 'limit': '10A', 'result': '9.8A'}
        ]
        entry = WorkItemEntry.objects.create(
            work_item=item,
            entry_type='supply',
            quantity=1,
            electrical_parameters=params
        )
        
        # Verify list of dicts saved and loaded correctly from JSONField
        fetched = WorkItemEntry.objects.get(pk=entry.pk)
        assert fetched.electrical_parameters == params
        assert fetched.electrical_parameters[0]['param'] == 'Voltage'
