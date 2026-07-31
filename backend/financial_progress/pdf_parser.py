import logging
import re
import pdfplumber

logger = logging.getLogger(__name__)

# Matches "Schedule A", "Schedule B", "Schedule A1", "Schedule B3", etc.
# Letter + optional digits, must be followed by non-alphanumeric (word boundary) to avoid "Schedule AMOUNT".
# Generalizes to any future letter (C, D, ...) without change — only the separator right after the
# letter/digit is assumed to be non-alphanumeric (a hyphen in every real bill seen so far); a bill
# that ran the schedule code directly into the next word with no separator would not match this.
SCHEDULE_RE = re.compile(r'Schedule\s+([A-Za-z]\d*)(?=[^A-Za-z0-9]|$)', re.IGNORECASE)
# Matches item-type cell like "1 (I)", "10 (I)", or a letter-prefixed convention like "NS01 (I)"
# ("Non-Schedule" items in some LOAs) — the prefix is kept as part of the item identity.
ITEM_NO_RE  = re.compile(r'^([A-Za-z]*\d+)\s*\([1Il]\)$', re.IGNORECASE)

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

    Rightmost column layout (right-to-left):
      Remarks (text, skip) | Total Up to Date | Amt incl. special condition | Amt since last Bill | ...

    Scan right-to-left through the last 6 cells, collect numerics:
      offset 0 = Total Up to Date  (cumulative, skip)
      offset 1 = Amt incl. special condition  ← prefer
      offset 2 = Amt since last Bill           ← fallback

    This approach is index-count-independent — robust when pdfplumber
    produces varying column counts across different PDF layouts.
    """
    tail = cells[-6:] if len(cells) >= 6 else cells
    numerics_rtl = []
    for c in reversed(tail):
        s = c.strip() if c else ''
        if s and _is_numeric(s):
            numerics_rtl.append(_to_float(s))

    if len(numerics_rtl) > 1 and numerics_rtl[1] > 0:
        return numerics_rtl[1]
    if len(numerics_rtl) > 2 and numerics_rtl[2] > 0:
        return numerics_rtl[2]
    return 0.0


def _parse_item_row(cells, current_schedule, warnings=None):
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

    # Agreement Rate (col 4) must be numeric
    if not _is_numeric(cells[4]):
        return None

    # Current Agmt Qty (col 6) must be numeric
    if not _is_numeric(cells[6]):
        return None

    # Item No. cell should match "N (I)" / "NS01 (I)" etc. A digit Sr.No plus numeric rate and
    # qty already make this structurally an item row regardless of the Item No. text's exact
    # format — item-numbering conventions vary by railway zone/vendor and will keep changing,
    # so an unrecognized format falls back to Sr.No as the item identity instead of dropping
    # real billed data. The LOA cross-check (views.py) still verifies/corrects identity from
    # description + qty afterward.
    item_raw = cells[1].strip()
    item_m = ITEM_NO_RE.match(item_raw)
    if item_m:
        item_no = item_m.group(1)
    else:
        item_no = sr
        if warnings is not None:
            warnings.append(
                f'Row sr={sr}: Item No "{item_raw}" format not recognized — '
                f'using Sr.No as item number, verify manually.'
            )

    unit = _normalize_unit(cells[2])
    if len(unit) > 40:
        unit = unit[:40]

    amt_total     = _find_total_amt(cells)
    qty_upto_date = _to_float(cells[9]) if len(cells) > 9 and _is_numeric(cells[9]) else 0.0
    remarks       = _clean(cells[14]) if len(cells) > 14 else ''
    # None (not 0.0) when blank/non-numeric — distinguishes "not present" from "genuinely
    # zero" for the LOA cross-check, which treats a missing qty as no signal rather than a
    # mismatch against every WorkItem.
    original_agmt_qty = _to_float(cells[5]) if _is_numeric(cells[5]) else None

    return {
        'schedule_name':      current_schedule,
        'item_number':        item_no,
        'description':        '',
        'unit':                unit,
        'agreement_rate':      _to_float(cells[4]),
        'original_agmt_qty':   original_agmt_qty,
        'current_agmt_qty':    _to_float(cells[6]),
        'qty_upto_date':       qty_upto_date,
        'amt_total':           amt_total,
        'remarks':             remarks,
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
                'original_agmt_qty': float or None,
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
            # Once True, stays True for the rest of the document. The trailing "Schedule
            # Summary" table restates each schedule's totals using the same "Schedule X" text
            # the header-detection below watches for — without this flag those summary rows
            # get misread as real section-header transitions and can corrupt current_schedule
            # for any item row that happens to follow on the same page.
            in_summary_section = False

            # Pages 2 onwards: item tables
            for page_num, page in enumerate(pdf.pages[1:], start=2):
                page_text = page.extract_text() or ''

                # Detect Schedule Summary page (usually last); still process for items
                if 'Schedule Summary' in page_text:
                    summary_page = page
                    # Don't skip — items 39/40 may be on this same page

                tables = page.extract_tables() or []
                for table_idx, table in enumerate(tables):
                    for row_idx, row in enumerate(table or []):
                        if not row:
                            continue

                        cells = [_clean(c) for c in row]
                        logger.debug('p%s t%s r%s sched=%s cells=%r', page_num, table_idx, row_idx, current_schedule, cells)

                        # ── Schedule Summary marker: stop treating "Schedule X" text as a
                        #    section-header cue from here on (see in_summary_section comment
                        #    above). Row-level, not page-level, since real item rows can still
                        #    legitimately appear earlier on this same page.
                        if cells[0].strip().lower().startswith('schedule summary'):
                            in_summary_section = True
                            continue

                        # ── Schedule section header ──────────────────────────
                        # Anchored to the START of cells[0], not searched across the whole
                        # row. Item descriptions routinely cross-reference another schedule
                        # in prose (e.g. "...pipe GI is covered in schedule A.)" or "SPMS
                        # charger is covered in schedule - A & VRLA battery...") — a row-wide
                        # search treats that mention as a section-header transition and
                        # silently mislabels every following item until the real header.
                        # Every genuine header row observed puts "Schedule X" at the very
                        # start of the first cell, so anchoring here is safe.
                        if not in_summary_section:
                            sched_m = SCHEDULE_RE.match(cells[0].strip())
                            if sched_m:
                                logger.debug('  -> SCHEDULE HEADER: %r -> %r', current_schedule, sched_m.group(1).upper())
                                current_schedule = sched_m.group(1).upper()
                                last_item = None
                                continue

                        # ── Total row: skip ──────────────────────────────────
                        if cells[0].strip().lower().startswith('total'):
                            continue

                        # ── Try to parse as item data row ────────────────────
                        item = _parse_item_row(cells, current_schedule, result['warnings'])
                        if item:
                            result['items'].append(item)
                            last_item = item
                            logger.debug('  -> ITEM sch=%s no=%s amt_total=%s', item['schedule_name'], item['item_number'], item['amt_total'])
                            continue

                        # ── Description continuation row ─────────────────────
                        if last_item and not in_summary_section and _is_description_row(cells):
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
