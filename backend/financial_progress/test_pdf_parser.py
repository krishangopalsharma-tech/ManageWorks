"""
Pure-Python tests for pdf_parser.py — no Django/DB needed.

pdfplumber.open() is mocked with a minimal fake page/pdf pair so parse_bill_pdf runs its real,
unmodified row-processing loop against literal Python cell-array fixtures. This lets us reproduce
exact pdfplumber output (captured once from a real production parse) without needing PDF bytes.
"""
import io

from financial_progress import pdf_parser
from financial_progress.pdf_parser import parse_bill_pdf, _parse_item_row


class _FakePage:
    def __init__(self, text='', tables=None):
        self._text = text
        self._tables = tables or []

    def extract_text(self):
        return self._text

    def extract_tables(self):
        return self._tables


class _FakePdf:
    def __init__(self, pages):
        self.pages = pages

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _fake_open_factory(pages):
    def _fake_open(file_obj):
        return _FakePdf(pages)
    return _fake_open


def _item_row(sr, item_no, agreement_rate, current_agmt_qty, amt_incl_special=0.0,
              total_upto_date=None, original_agmt_qty=None):
    """Build a structurally valid 15-cell item row (matches the documented column layout)."""
    total_upto_date = amt_incl_special if total_upto_date is None else total_upto_date
    col5 = current_agmt_qty if original_agmt_qty is None else original_agmt_qty
    return [
        str(sr), f'{item_no} (I)', 'Numbers', '10', str(agreement_rate),
        str(col5), str(current_agmt_qty), '0', '0', '0',
        '0', '0', str(amt_incl_special), str(total_upto_date), '',
    ]


def _header_row(label):
    return [label, '', '', '']


def _parse(rows, monkeypatch):
    page1 = _FakePage(text='Bill No.WR/TEST/0001', tables=[])
    page2 = _FakePage(text='', tables=[rows])
    monkeypatch.setattr(pdf_parser.pdfplumber, 'open', _fake_open_factory([page1, page2]))
    return parse_bill_pdf(io.BytesIO(b'irrelevant'))


def test_schedule_summary_table_does_not_corrupt_current_schedule(monkeypatch):
    rows = [
        _header_row('Schedule B-SUPPLY AND INSTALLATION'),
        _item_row(1, 1, 100, 5, amt_incl_special=500),
        _header_row('Schedule A-SUPPLY'),
        _item_row(1, 1, 140, 5, amt_incl_special=700),
        _header_row('Schedule Summary:'),
        ['Schedule B-SUPPLY AND INSTALLATION', '0.0', '0.0', '0.0'],
        ['Schedule A-SUPPLY', '0.0', '700.0', '700.0'],
        # A real trailing item row sharing the page with the Schedule Summary table
        # (the code's own comment says this can happen) — must stay tagged 'A',
        # not get corrupted by the summary rows' "Schedule B" / "Schedule A" text.
        _item_row(2, 2, 60, 5, amt_incl_special=300),
    ]
    result = _parse(rows, monkeypatch)

    assert [i['schedule_name'] for i in result['items']] == ['B', 'A', 'A']
    assert result['items'][2]['amt_total'] == 300


def test_schedule_summary_marker_row_not_appended_to_description(monkeypatch):
    rows = [
        _header_row('Schedule A-SUPPLY'),
        _item_row(1, 1, 140, 5, amt_incl_special=700),
        _header_row('Schedule Summary:'),
        ['Schedule A-SUPPLY', '0.0', '700.0', '700.0'],
    ]
    result = _parse(rows, monkeypatch)

    assert len(result['items']) == 1
    assert 'Schedule' not in result['items'][0]['description']
    assert result['items'][0]['description'] == ''


def test_multi_letter_schedule_header_recognized(monkeypatch):
    # "Schedule NS-NON SCHEDULE ITEMS" — a two-letter code. The old single-letter-only regex
    # failed to match this at all, so the header row was never recognized and NS items
    # silently inherited whatever schedule came before them (the real production bug).
    rows = [
        _header_row('Schedule A-SUPPLY'),
        _item_row(1, 1, 100, 5, amt_incl_special=500),
        _header_row('Schedule NS-NON SCHEDULE ITEMS'),
        _item_row(1, 'NS01', 100, 2, amt_incl_special=50),
        _item_row(2, 'NS02', 200, 1, amt_incl_special=60),
    ]
    result = _parse(rows, monkeypatch)

    assert [i['schedule_name'] for i in result['items']] == ['A', 'NS', 'NS']
    assert [i['item_number'] for i in result['items']] == ['1', 'NS01', 'NS02']


def test_letter_prefixed_item_number_parsed(monkeypatch):
    # "Non-Schedule" (NS) items in some LOAs use a letter-prefixed item number instead of a
    # plain digit — must not be dropped, and the prefix is kept as part of the identity.
    rows = [
        _header_row('Schedule NS-NON SCHEDULE ITEMS'),
        _item_row(1, 'NS01', 100, 2, amt_incl_special=50),
        _item_row(2, 'NS02', 200, 1, amt_incl_special=60),
    ]
    result = _parse(rows, monkeypatch)

    assert [i['item_number'] for i in result['items']] == ['NS01', 'NS02']
    assert not any('failed regex' in w for w in result['warnings'])


def test_unrecognized_item_number_format_falls_back_to_sr_no():
    # Structurally a valid item row (digit Sr.No, numeric rate + qty) but the Item No. cell
    # matches neither the digit nor letter-prefix pattern — kept and flagged, not dropped.
    cells = [
        '5', '5/A (I)', 'Numbers', '10', '100',
        '2', '2', '0', '0', '0', '0', '0', '200', '200', '',
    ]
    item = _parse_item_row(cells, 'A', warnings=(warnings := []))

    assert item is not None
    assert item['item_number'] == '5'
    assert any('format not recognized' in w for w in warnings)


def test_schedule_letter_generalizes_beyond_a_and_b(monkeypatch):
    rows = [
        _header_row('Schedule C-SUPPLY'),
        _item_row(1, 1, 100, 2, amt_incl_special=50),
        _header_row('Schedule D1-SUPPLY'),
        _item_row(1, 1, 100, 2, amt_incl_special=60),
    ]
    result = _parse(rows, monkeypatch)

    assert [i['schedule_name'] for i in result['items']] == ['C', 'D1']


def test_section_order_independence(monkeypatch):
    b_then_a = [
        _header_row('Schedule B-SUPPLY'),
        _item_row(1, 1, 100, 2, amt_incl_special=10),
        _header_row('Schedule A-SUPPLY'),
        _item_row(1, 1, 100, 2, amt_incl_special=20),
    ]
    a_then_b = [
        _header_row('Schedule A-SUPPLY'),
        _item_row(1, 1, 100, 2, amt_incl_special=30),
        _header_row('Schedule B-SUPPLY'),
        _item_row(1, 1, 100, 2, amt_incl_special=40),
    ]

    result1 = _parse(b_then_a, monkeypatch)
    assert [i['schedule_name'] for i in result1['items']] == ['B', 'A']

    result2 = _parse(a_then_b, monkeypatch)
    assert [i['schedule_name'] for i in result2['items']] == ['A', 'B']


def test_original_agmt_qty_extracted_from_column_5(monkeypatch):
    rows = [
        _header_row('Schedule A-SUPPLY'),
        _item_row(1, 1, 100, current_agmt_qty=5, original_agmt_qty=8, amt_incl_special=500),
    ]
    result = _parse(rows, monkeypatch)

    assert result['items'][0]['original_agmt_qty'] == 8.0
    assert result['items'][0]['current_agmt_qty'] == 5.0


def test_original_agmt_qty_none_when_column_blank_or_non_numeric():
    cells = [
        '1', '1 (I)', 'Numbers', '10', '100',
        '', '5', '0', '0', '0', '0', '0', '500', '500', '',
    ]
    item = _parse_item_row(cells, 'A', warnings=[])
    assert item['original_agmt_qty'] is None


def test_description_row_that_mentions_another_schedule_does_not_flip_current_schedule(monkeypatch):
    # Real bug: item descriptions routinely cross-reference another schedule in prose,
    # e.g. "...Other pipes will be supplied by Rlys...(Supply of DWC/RCC/HDPE pipe GI is
    # covered in schedule A.) Other pipes..." A row-wide search for "Schedule X" treated
    # that mention as a section-header transition and silently mislabeled every following
    # Schedule B item as 'A' for the rest of the document.
    rows = [
        _header_row('Schedule B-SUPPLY & INSTALLATION'),
        _item_row(16, 16, 30, 4250, amt_incl_special=0),
        ['Placing of DWC/ RCC / HDPE pipe in trench for track / road crossing. (Supply of '
         'DWC/ RCC / HDPE pipe GI is covered in schedule A.) Other pipes will be supplied '
         'by Rlys.', '', '', ''],
        _item_row(17, 17, 302, 2505, amt_incl_special=0),
    ]
    result = _parse(rows, monkeypatch)

    assert [i['schedule_name'] for i in result['items']] == ['B', 'B']
    assert 'schedule A' in result['items'][0]['description']


def test_long_description_with_embedded_numbered_sublist_not_misparsed_as_item_row():
    # A continuation row where the description happens to start with a digit-like fragment
    # ("1 Supply of ... 2 Supply of ...") must never be mistaken for a new item row — the
    # Item No. cell (index 1) won't match the strict "N (I)" pattern, so it's correctly skipped.
    cells = [
        '1', '1 Supply of High Back Revolving Chair 4 Nos 2 Supply of Revolving Chair 10 Nos',
        '', '', '', '', '', '', '', '', '', '', '', '', '',
    ]
    assert _parse_item_row(cells, 'B3', warnings=[]) is None
