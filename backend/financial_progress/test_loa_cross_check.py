import pytest
from django.contrib.auth.models import User

from users.models import UserProfile
from works.models import Work, WorkItem
from financial_progress.views import _build_loa_lookup, _loa_cross_check, _normalize_serial


@pytest.mark.django_db
class TestLoaCrossCheck:

    @pytest.fixture(autouse=True)
    def setup_data(self):
        consignee = User.objects.create_user(username='consignee1', password='password123')
        UserProfile.objects.create(user=consignee, designation='Consignee', is_approved=True, role='consignee')
        self.work = Work.objects.create(loa_number='LOA-2026-001', contractor_name='Apex', hrms_id='consignee1')

    def test_same_item_number_different_schedules_cross_checked_independently(self):
        # Same serial_number ('1'), different schedules — must not collide.
        WorkItem.objects.create(work=self.work, schedule='A', serial_number='1', total_amount=1000)
        WorkItem.objects.create(work=self.work, schedule='B', serial_number='1', total_amount=50000)

        parsed = {
            'items': [
                {'schedule_name': 'A', 'item_number': '1', 'amt_total': 900},
                {'schedule_name': 'B', 'item_number': '1', 'amt_total': 45000},
            ],
            'warnings': [],
        }
        loa_lookup = _build_loa_lookup(self.work)
        _loa_cross_check(parsed, loa_lookup)

        assert parsed['items'][0]['loa_contract_value'] == 1000
        assert parsed['items'][1]['loa_contract_value'] == 50000
        # Neither item exceeds its own schedule's contract value — no overpayment warning.
        assert not any('Overpayment' in w for w in parsed['warnings'])

    def test_overpayment_flagged_against_the_correct_schedule_only(self):
        WorkItem.objects.create(work=self.work, schedule='A', serial_number='18', total_amount=3165)
        WorkItem.objects.create(work=self.work, schedule='B', serial_number='18', total_amount=400000)

        parsed = {
            'items': [
                # Paying more than Schedule A item 18's own contract value — should warn.
                {'schedule_name': 'A', 'item_number': '18', 'amt_total': 322708},
                # Same amount is well within Schedule B item 18's contract value — no warning.
                {'schedule_name': 'B', 'item_number': '18', 'amt_total': 322708},
            ],
            'warnings': [],
        }
        loa_lookup = _build_loa_lookup(self.work)
        _loa_cross_check(parsed, loa_lookup)

        warnings_text = ' '.join(parsed['warnings'])
        assert 'Sch A Item 18' in warnings_text
        assert 'Sch B Item 18' not in warnings_text

    def test_serial_number_zero_padding_normalization(self):
        assert _normalize_serial('01') == _normalize_serial('1') == '1'

        WorkItem.objects.create(work=self.work, schedule='A', serial_number='1', total_amount=500)
        parsed = {
            'items': [{'schedule_name': 'A', 'item_number': '01', 'amt_total': 100}],
            'warnings': [],
        }
        loa_lookup = _build_loa_lookup(self.work)
        _loa_cross_check(parsed, loa_lookup)

        assert parsed['items'][0]['loa_contract_value'] == 500
        assert not parsed['warnings']

    def test_self_heals_item_mislabeled_into_wrong_schedule_via_description_and_qty(self):
        # Reproduces the real production bug shape: an item that actually belongs to
        # schedule A gets parsed with schedule_name='B' (e.g. a schedule-header regex
        # false-positive), but its description/qty clearly match A's item, not B's.
        WorkItem.objects.create(
            work=self.work, schedule='A', serial_number='5',
            item_desc='Supply of GI pipe fitting as per technical specification.',
            qty=12, total_amount=6000,
        )
        WorkItem.objects.create(
            work=self.work, schedule='B', serial_number='5',
            item_desc='Installation of cable tray with all accessories.',
            qty=40, total_amount=90000,
        )

        parsed = {
            'items': [{
                'schedule_name': 'B',  # wrongly claimed
                'item_number': '5',
                'description': 'Supply of GI pipe fitting as per technical specification.',
                'original_agmt_qty': 12,
                'amt_total': 5000,
            }],
            'warnings': [],
        }
        loa_lookup = _build_loa_lookup(self.work)
        _loa_cross_check(parsed, loa_lookup)

        assert parsed['items'][0]['schedule_name'] == 'A'
        assert parsed['items'][0]['loa_contract_value'] == 6000
        assert any('Auto-corrected' in w for w in parsed['warnings'])
        assert not any('Overpayment' in w for w in parsed['warnings'])
        assert not any('not found in LOA' in w for w in parsed['warnings'])

    def test_does_not_relabel_when_current_schedule_already_correct(self):
        WorkItem.objects.create(
            work=self.work, schedule='A', serial_number='5',
            item_desc='Supply of GI pipe fitting as per technical specification.',
            qty=12, total_amount=6000,
        )
        WorkItem.objects.create(
            work=self.work, schedule='B', serial_number='5',
            item_desc='Installation of cable tray with all accessories.',
            qty=40, total_amount=90000,
        )

        parsed = {
            'items': [{
                'schedule_name': 'A',  # correctly claimed
                'item_number': '5',
                'description': 'Supply of GI pipe fitting as per technical specification.',
                'original_agmt_qty': 12,
                'amt_total': 5000,
            }],
            'warnings': [],
        }
        loa_lookup = _build_loa_lookup(self.work)
        _loa_cross_check(parsed, loa_lookup)

        assert parsed['items'][0]['schedule_name'] == 'A'
        assert not any('Auto-corrected' in w for w in parsed['warnings'])

    def test_ambiguous_candidates_flagged_for_manual_verification_not_auto_healed(self):
        # Item claims schedule 'B' (no WorkItem exists there at this serial — e.g. mislabeled),
        # but two other schedules (A1, A2) tie for the best match — neither should be
        # auto-picked; must flag for manual review instead of guessing between them.
        WorkItem.objects.create(
            work=self.work, schedule='A1', serial_number='9',
            item_desc='Supply of connectors and patch cords as per specification.',
            qty=15, total_amount=2000,
        )
        WorkItem.objects.create(
            work=self.work, schedule='A2', serial_number='9',
            item_desc='Supply of connectors and patch cords as per specification.',
            qty=15, total_amount=2500,
        )

        parsed = {
            'items': [{
                'schedule_name': 'B',
                'item_number': '9',
                'description': 'Supply of connectors and patch cords as per specification.',
                'original_agmt_qty': 15,
                'amt_total': 1000,
            }],
            'warnings': [],
        }
        loa_lookup = _build_loa_lookup(self.work)
        _loa_cross_check(parsed, loa_lookup)

        assert parsed['items'][0]['schedule_name'] == 'B'
        assert any('Ambiguous' in w for w in parsed['warnings'])

    def test_no_signal_available_falls_back_to_existing_behavior(self):
        # No description, no original_agmt_qty parsed (e.g. older bill/parser) — must behave
        # exactly like today: no relabeling, no new warnings, plain lookup match.
        WorkItem.objects.create(work=self.work, schedule='A', serial_number='7', total_amount=1200)
        WorkItem.objects.create(work=self.work, schedule='B', serial_number='7', total_amount=8000)

        parsed = {
            'items': [{'schedule_name': 'A', 'item_number': '7', 'amt_total': 1100}],
            'warnings': [],
        }
        loa_lookup = _build_loa_lookup(self.work)
        _loa_cross_check(parsed, loa_lookup)

        assert parsed['items'][0]['schedule_name'] == 'A'
        assert parsed['items'][0]['loa_contract_value'] == 1200
        assert not parsed['warnings']

    def test_low_confidence_match_flagged_without_relabeling_or_dropping_when_no_better_candidate(self):
        WorkItem.objects.create(
            work=self.work, schedule='A', serial_number='3',
            item_desc='Supply of 4TB HDD Hard disk for NVR as per Technical Specification.',
            qty=4, total_amount=44000,
        )

        parsed = {
            'items': [{
                'schedule_name': 'A',
                'item_number': '3',
                'description': 'Excavation of cable trench alongside the track.',
                'original_agmt_qty': 2505,
                'amt_total': 1000,
            }],
            'warnings': [],
        }
        loa_lookup = _build_loa_lookup(self.work)
        _loa_cross_check(parsed, loa_lookup)

        # Kept, not dropped — only flagged.
        assert parsed['items'][0]['schedule_name'] == 'A'
        assert parsed['items'][0]['loa_contract_value'] == 44000
        assert any('Low-confidence' in w for w in parsed['warnings'])

    def test_overpayment_detected_against_the_self_healed_schedule(self):
        WorkItem.objects.create(
            work=self.work, schedule='A', serial_number='5',
            item_desc='Supply of GI pipe fitting as per technical specification.',
            qty=12, total_amount=1000,
        )
        WorkItem.objects.create(
            work=self.work, schedule='B', serial_number='5',
            item_desc='Installation of cable tray with all accessories.',
            qty=40, total_amount=90000,
        )

        parsed = {
            'items': [{
                'schedule_name': 'B',  # wrongly claimed; will heal to A
                'item_number': '5',
                'description': 'Supply of GI pipe fitting as per technical specification.',
                'original_agmt_qty': 12,
                'amt_total': 1500,  # exceeds A's contract value (1000), not B's (90000)
            }],
            'warnings': [],
        }
        loa_lookup = _build_loa_lookup(self.work)
        _loa_cross_check(parsed, loa_lookup)

        assert parsed['items'][0]['schedule_name'] == 'A'
        warnings_text = ' '.join(parsed['warnings'])
        assert 'Overpayment' in warnings_text and 'Sch A Item 5' in warnings_text

    def test_true_duplicate_across_schedules_kept_as_is_when_current_already_ties_for_best(self):
        # Two WorkItems identical on every scored signal (desc, qty, unit, rate) across
        # different schedules — genuinely no data left to distinguish them. The parsed item
        # correctly claims 'A' (i.e. the PDF's own section placement, which header-tracking
        # already got right) — since 'A' already ties for the best possible score, there's
        # nothing to heal and nothing ambiguous to flag.
        WorkItem.objects.create(
            work=self.work, schedule='A', serial_number='6',
            item_desc='Supply of RJ-45 connectors as per Technical Specification.',
            qty=220, unit='Numbers', unit_rate_rs=11.9, unit_rate_below=0, total_amount=2618,
        )
        WorkItem.objects.create(
            work=self.work, schedule='B', serial_number='6',
            item_desc='Supply of RJ-45 connectors as per Technical Specification.',
            qty=220, unit='Numbers', unit_rate_rs=11.9, unit_rate_below=0, total_amount=2618,
        )

        parsed = {
            'items': [{
                'schedule_name': 'A',
                'item_number': '6',
                'description': 'Supply of RJ-45 connectors as per Technical Specification.',
                'original_agmt_qty': 220,
                'unit': 'Numbers',
                'agreement_rate': 11.9,
                'amt_total': 1000,
            }],
            'warnings': [],
        }
        loa_lookup = _build_loa_lookup(self.work)
        _loa_cross_check(parsed, loa_lookup)

        assert parsed['items'][0]['schedule_name'] == 'A'
        assert not parsed['warnings']

    def test_unit_or_rate_breaks_a_desc_qty_tie(self):
        # Same description + qty across two schedules, but unit/rate differ — the parsed
        # item's unit/rate matches schedule B specifically, so it's no longer a real tie.
        WorkItem.objects.create(
            work=self.work, schedule='A', serial_number='8',
            item_desc='Supply of connectors as per specification.',
            qty=50, unit='Numbers', unit_rate_rs=100, unit_rate_below=0, total_amount=5000,
        )
        WorkItem.objects.create(
            work=self.work, schedule='B', serial_number='8',
            item_desc='Supply of connectors as per specification.',
            qty=50, unit='Metre', unit_rate_rs=200, unit_rate_below=0, total_amount=10000,
        )

        parsed = {
            'items': [{
                'schedule_name': 'C',  # wrongly claimed; no WorkItem exists at (C, 8)
                'item_number': '8',
                'description': 'Supply of connectors as per specification.',
                'original_agmt_qty': 50,
                'unit': 'Metre',
                'agreement_rate': 200,
                'amt_total': 1000,
            }],
            'warnings': [],
        }
        loa_lookup = _build_loa_lookup(self.work)
        _loa_cross_check(parsed, loa_lookup)

        assert parsed['items'][0]['schedule_name'] == 'B'
        assert not any('Ambiguous' in w for w in parsed['warnings'])
        assert any('Auto-corrected' in w for w in parsed['warnings'])
