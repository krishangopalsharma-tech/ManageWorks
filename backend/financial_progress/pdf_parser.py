import re
import pdfplumber


# Matches "Schedule A", "Schedule B", "Schedule A1", "Schedule B3", etc.
# Letter + optional digits, must be followed by non-alphanumeric (word boundary) to avoid "Schedule AMOUNT"
SCHEDULE_RE = re.compile(r'Schedule\s+([A-Za-z]\d*)(?=[^A-Za-z0-9]|$)', re.IGNORECASE)
# Matches item-type cell like "1 (I)" or "10 (I)"
ITEM_NO_RE  = re.compile(r'^(\d+)\s*\(I\)$')


def _clean(val):
    if val is None:
        return ''
    return str(val).strip().replace('\n', ' ')


def _unwrap_number(s):
    """
    Fix PDF line-wrapped numbers that pdfplumber returns with embedded spaces.

    Examples (cell value spans two lines inside the PDF cell):
      "1593387. 35"  → "1593387.35"   (digit-dot-space-digits)
      "174775.7 1"   → "174775.71"    (digit-space-digit after decimal)
      "8650. 0"      → "8650.0"
      "1991734. 19"  → "1991734.19"
    """
    # Step 1: "NNN. DDD" – space immediately after the decimal point
    s = re.sub(r'(\d+\.)\s+(\d)', r'\1\2', s)
    # Step 2: "NNN.D DD" – space between decimal digit groups
    s = re.sub(r'(\d)\s+(\d)', r'\1\2', s)
    return s


def _to_float(s):
    if not s:
        return 0.0
    s = _clean(s).replace(',', '').strip()
    try:
        return float(s)
    except (ValueError, TypeError):
        try:
            return float(_unwrap_number(s))
        except (ValueError, TypeError):
            return 0.0


def _is_numeric(s):
    s = _clean(s).replace(',', '').strip()
    try:
        float(s)
        return True
    except (ValueError, TypeError):
        try:
            float(_unwrap_number(s))
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


def _find_total_amt(cells):
    """
    Extract the CURRENT PERIOD payment (not cumulative) from amount columns.

    Column layout (0-indexed):
      10  Amt upto last Bill          ← previous bills cumulative
      11  Amt since last Bill         ← current period, full rate
      12  Amt since last Bill incl.   ← current period with special condition
          special condition             (highlighted cyan in PDF = what to pay now)
      13  Total Up to Date Amount     ← cumulative; NOT used (inflates multi-bill totals)

    We want col 12 (highlighted cell) → fallback col 11.
    """
    n = len(cells)
    # Preferred: col 12 = current period with special condition (highlighted cell)
    if n > 12 and _is_numeric(cells[12]) and _to_float(cells[12]) > 0:
        return _to_float(cells[12])
    # Fallback: col 11 = current period without special condition
    if n > 11 and _is_numeric(cells[11]) and _to_float(cells[11]) > 0:
        return _to_float(cells[11])
    return 0.0


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
      12 Amt since last Bill incl. special condition
      13 Total Up to Date Amount   ← we want this
      14 Remarks (optional)

    Returns dict or None.
    """
    if len(cells) < 11:
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

    unit = _normalize_unit(cells[2])
    if len(unit) > 40:
        unit = unit[:40]

    amt_total     = _find_total_amt(cells)
    qty_upto_date = _to_float(cells[9]) if len(cells) > 9 and _is_numeric(cells[9]) else 0.0
    remarks       = _clean(cells[14]) if len(cells) > 14 else ''

    return {
        'schedule_name':    current_schedule,
        'item_number':      item_no,
        'description':      '',
        'unit':             unit,
        'agreement_rate':   _to_float(cells[4]),
        'current_agmt_qty': _to_float(cells[6]),
        'qty_upto_date':    qty_upto_date,
        'amt_total':        amt_total,
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
            summary_page = None  # cache Schedule Summary page for cross-check

            # Pages 2 onwards: item tables
            for page_num, page in enumerate(pdf.pages[1:], start=2):
                page_text = page.extract_text() or ''

                # Detect Schedule Summary page (usually last); still process for items
                if 'Schedule Summary' in page_text:
                    summary_page = page
                    # Don't skip — items 39/40 may be on this same page

                tables = page.extract_tables() or []
                for table in tables:
                    for row in (table or []):
                        if not row:
                            continue

                        cells = [_clean(c) for c in row]
                        row_text = ' '.join(cells)

                        # ── Schedule section header ──────────────────────────
                        sched_m = SCHEDULE_RE.search(row_text)
                        if not sched_m:
                            # Fallback: single-letter schedule like "Schedule A" or "Schedule B"
                            sched_m = re.search(r'Schedule\s+([A-Za-z]\d*)(?=[^A-Za-z0-9]|$)', row_text, re.IGNORECASE)
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

            # ── Cross-check against Schedule Summary ────────────────────────
            if summary_page and result['items']:
                _cross_check_summary(summary_page, result)

    except Exception as exc:
        result['warnings'].append(f'Parse error: {exc}')

    if not result['items']:
        result['warnings'].append('No item rows extracted. PDF format may differ from expected.')

    return result


def _cross_check_summary(summary_page, result):
    """
    Parse the Schedule Summary table on the last page.
    Extract the grand total from the "Total Amount(Rs.)" row — single comparison,
    no per-schedule fragility (multi-line schedule names would break per-schedule regex).
    """
    grand_pdf = None

    # Try table extraction first (more reliable than text for structured tables)
    total_amount_fallback = None
    for table in (summary_page.extract_tables() or []):
        for row in (table or []):
            cells = [_clean(c) for c in (row or [])]
            row_text = ' '.join(cells).lower()
            # "Bill Amount" = authoritative current-bill total (period payment only)
            if 'bill amount' in row_text:
                nums = [_to_float(c) for c in cells if _is_numeric(c) and _to_float(c) > 0]
                if nums:
                    grand_pdf = nums[-1]
                    break
            # "Total Amount(Rs.)" row — keep as fallback, use middle col (period) not last (cumulative)
            if 'total amount' in row_text and 'rs' in row_text and total_amount_fallback is None:
                nums = [_to_float(c) for c in cells if _is_numeric(c) and _to_float(c) > 0]
                if len(nums) >= 2:
                    total_amount_fallback = nums[-2]  # second-to-last = "Amt incl Special Condition"
                elif nums:
                    total_amount_fallback = nums[-1]
        if grand_pdf is not None:
            break

    if grand_pdf is None:
        grand_pdf = total_amount_fallback

    # Fallback: scan page text for "Total Amount" line
    if grand_pdf is None:
        page_text = summary_page.extract_text() or ''
        for line in page_text.splitlines():
            ll = line.lower()
            if 'total amount' in ll and 'rs' in ll:
                nums = re.findall(r'\d[\d,]*\.?\d*', line)
                positives = [float(n.replace(',', '')) for n in nums if float(n.replace(',', '')) > 0]
                if positives:
                    grand_pdf = positives[-1]
                    break

    if grand_pdf is None:
        return

    grand_parse = round(sum(item['amt_total'] for item in result['items']), 2)
    grand_pdf   = round(grand_pdf, 2)
    result['pdf_grand_total'] = grand_pdf

    if abs(grand_parse - grand_pdf) > 1.0:
        result['warnings'].append(
            f'Grand total mismatch: PDF={grand_pdf:,.2f}, parsed={grand_parse:,.2f}. '
            'Check items above.'
        )
