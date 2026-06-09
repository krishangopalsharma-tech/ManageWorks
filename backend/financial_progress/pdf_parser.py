import re
import pdfplumber


# Matches schedule headers like "Schedule B3-SCHEDULE" or "Schedule A1"
SCHEDULE_RE = re.compile(r'Schedule\s+((?:A|B)\d+)(?:-SCHEDULE)?', re.IGNORECASE)
# Matches item-type cell like "1 (I)" or "10 (I)"
ITEM_NO_RE  = re.compile(r'^(\d+)\s*\(I\)$')


def _clean(val):
    if val is None:
        return ''
    return str(val).strip().replace('\n', ' ')


def _to_float(s):
    if not s:
        return 0.0
    s = _clean(s).replace(',', '').strip()
    try:
        return float(s)
    except (ValueError, TypeError):
        return 0.0


def _is_numeric(s):
    s = _clean(s).replace(',', '')
    try:
        float(s)
        return True
    except (ValueError, TypeError):
        return False


def _normalize_unit(raw):
    """Clean up unit strings like 'Runn ing Metre' → 'Running Metre'."""
    if not raw:
        return ''
    cleaned = re.sub(r'\s+', ' ', raw.strip())
    # Collapse broken words: "Runn ing" → "Running", "Num bers" → "Numbers"
    cleaned = re.sub(r'([A-Za-z]{2,})\s([a-z]{2,})', lambda m: m.group(1) + m.group(2), cleaned)
    return cleaned


def _extract_header_info(pdf):
    """Extract bill_number, bill_date, loa_number, agreement_number from page 1."""
    result = {'bill_number': '', 'bill_date': '', 'loa_number': '', 'agreement_number': ''}
    page1 = pdf.pages[0]

    # Try from page text first
    text = page1.extract_text() or ''
    m = re.search(r'Bill No[.\s]*([^\n]+)', text, re.IGNORECASE)
    if m:
        result['bill_number'] = m.group(1).strip()

    # Try from tables (key-value pairs)
    tables = page1.extract_tables() or []
    for table in tables:
        for row in (table or []):
            cells = [_clean(c) for c in (row or [])]
            for i in range(len(cells) - 1):
                label = cells[i].lower()
                val   = cells[i + 1]
                if not val:
                    continue
                if 'agreement no' in label:
                    result['agreement_number'] = val
                elif 'loa no' in label:
                    result['loa_number'] = val
                elif 'bill date' in label:
                    result['bill_date'] = _parse_date(val)

    # Also grab bill number from text "Bill No.WR/ADI/..."
    if not result['bill_number']:
        m = re.search(r'Bill No\.(\S+)', text)
        if m:
            result['bill_number'] = m.group(1)

    return result


def _parse_date(val):
    val = _clean(val)
    # DD/MM/YYYY
    m = re.match(r'^(\d{1,2})/(\d{1,2})/(\d{4})$', val)
    if m:
        return f"{m.group(3)}-{m.group(2).zfill(2)}-{m.group(1).zfill(2)}"
    # DD-MM-YYYY
    m = re.match(r'^(\d{1,2})-(\d{1,2})-(\d{4})$', val)
    if m:
        return f"{m.group(3)}-{m.group(2).zfill(2)}-{m.group(1).zfill(2)}"
    return val


def _parse_item_row(cells, current_schedule):
    """
    Try to parse a table row as a bill item.

    Expected columns (0-indexed):
      0  Sr.No
      1  Item No. (ItemType)   e.g. "1 (I)"
      2  Unit/Description
      3  Base Rate
      4  Agreement Rate
      5  Original Agmt Qty
      6  Current Agmt Qty
      7  Qty upto last Bill
      8  Qty since last Bill
      9  Qty Upto Date
      10 Amt upto last Bill
      11 Amt since last Bill
      12 Amt since last Bill incl. special condition  (ignored)
      13 Total Up to Date Amount   ← we want this
      14 Remarks (optional)

    Returns dict or None.
    """
    if len(cells) < 14:
        return None

    # Sr.No must be a plain integer
    sr = cells[0].strip()
    if not sr.isdigit():
        return None

    # Item No. cell must match "N (I)"
    item_raw = cells[1].strip()
    item_m = ITEM_NO_RE.match(item_raw)
    if not item_m:
        return None

    item_no = item_m.group(1)

    # Agreement Rate (col 4) must be numeric
    if not _is_numeric(cells[4]):
        return None

    # Current Agmt Qty (col 6) must be numeric
    if not _is_numeric(cells[6]):
        return None

    # Total Upto Date (col 13) must be numeric
    if not _is_numeric(cells[13]):
        return None

    unit = _normalize_unit(cells[2])
    # If unit cell contains a long description (>40 chars), truncate to first word segment
    if len(unit) > 40:
        unit = unit[:40]

    remarks = _clean(cells[14]) if len(cells) > 14 else ''

    return {
        'schedule_name':    current_schedule,
        'item_number':      item_no,
        'description':      '',
        'unit':             unit,
        'agreement_rate':   _to_float(cells[4]),
        'current_agmt_qty': _to_float(cells[6]),
        'amt_total':        _to_float(cells[13]),
        'remarks':          remarks,
    }


def _is_description_row(cells):
    """True if row has no numeric content — it's a description continuation row."""
    non_empty = [c for c in cells if c.strip()]
    if not non_empty:
        return False
    # If any numeric values, it's not purely a description row
    numeric_count = sum(1 for c in non_empty if _is_numeric(c))
    return numeric_count == 0


def parse_bill_pdf(file_obj):
    """
    Parse a railway bill PDF.

    Returns:
        {
          'bill_number': str,
          'bill_date': str (YYYY-MM-DD),
          'loa_number': str,
          'agreement_number': str,
          'items': [
              {
                'schedule_name': 'B3',
                'item_number': '10',
                'description': str,
                'unit': str,
                'agreement_rate': float,
                'current_agmt_qty': float,
                'amt_total': float,
                'remarks': str,
              }, ...
          ],
          'warnings': [str, ...],
        }
    """
    result = {
        'bill_number': '',
        'bill_date': '',
        'loa_number': '',
        'agreement_number': '',
        'items': [],
        'warnings': [],
    }

    try:
        with pdfplumber.open(file_obj) as pdf:
            if not pdf.pages:
                result['warnings'].append('PDF has no pages.')
                return result

            # Page 1: header info
            header = _extract_header_info(pdf)
            result.update(header)

            current_schedule = 'UNKNOWN'
            last_item = None

            # Pages 2 onwards: item tables
            for page_num, page in enumerate(pdf.pages[1:], start=2):
                page_text = page.extract_text() or ''

                # Skip Schedule Summary page (usually last page)
                if 'Schedule Summary' in page_text and page_num >= len(pdf.pages) - 1:
                    continue

                tables = page.extract_tables() or []
                for table in tables:
                    for row in (table or []):
                        if not row:
                            continue

                        cells = [_clean(c) for c in row]
                        row_text = ' '.join(cells)

                        # ── Schedule section header ──────────────────────────
                        sched_m = SCHEDULE_RE.search(row_text)
                        if sched_m:
                            first = cells[0].strip().lower()
                            if not first.startswith('total'):
                                current_schedule = sched_m.group(1).upper()
                                last_item = None
                                continue

                        # ── Total row: skip ──────────────────────────────────
                        if cells[0].strip().lower().startswith('total'):
                            continue

                        # ── Try to parse as item data row ────────────────────
                        item = _parse_item_row(cells, current_schedule)
                        if item:
                            result['items'].append(item)
                            last_item = item
                            continue

                        # ── Description continuation row ─────────────────────
                        if last_item and _is_description_row(cells):
                            desc_text = ' '.join(c for c in cells if c.strip())
                            desc_text = desc_text.strip()
                            if desc_text:
                                if last_item['description']:
                                    last_item['description'] += ' ' + desc_text
                                else:
                                    last_item['description'] = desc_text

    except Exception as exc:
        result['warnings'].append(f'Parse error: {exc}')

    if not result['items']:
        result['warnings'].append('No item rows extracted. PDF format may differ from expected.')

    return result
