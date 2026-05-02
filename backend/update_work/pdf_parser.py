import re
import pdfplumber


def _parse_date(date_str):
    """Convert DD-MM-YYYY → YYYY-MM-DD. Pass through YYYY-MM-DD unchanged."""
    if not date_str:
        return None
    date_str = date_str.strip()
    m = re.match(r'^(\d{1,2})-(\d{1,2})-(\d{4})$', date_str)
    if m:
        return f"{m.group(3)}-{m.group(2).zfill(2)}-{m.group(1).zfill(2)}"
    m = re.match(r'^(\d{4})-(\d{2})-(\d{2})$', date_str)
    if m:
        return date_str
    return date_str


def _clean_sno(val):
    """Strip trailing dashes, slashes, spaces from serial/item numbers."""
    val = val.strip()
    val = re.sub(r'[\s\-/]+$', '', val)
    return val


def _clean_desc(val):
    """Strip surrounding quotes/smart-quotes and normalise whitespace."""
    val = val.strip()
    val = re.sub(r'^[“”‘’"\']+|[“”‘’"\']+$', '', val)
    val = re.sub(r'\s+', ' ', val).strip()
    return val


def _table_label_values(pdf):
    """Extract label→value pairs from PDF tables (handles 2- and 4-column rows)."""
    lv = {}
    for page in pdf.pages:
        tables = page.extract_tables() or []
        for table in tables:
            for row in (table or []):
                if not row:
                    continue
                cells = [str(c).strip().replace('\n', ' ') if c else '' for c in row]
                # Pair cells as (label, value) stepping by 2
                for i in range(0, len(cells) - 1, 2):
                    lbl = cells[i].strip()
                    val = cells[i + 1] if i + 1 < len(cells) else ''
                    if lbl:
                        lv[lbl] = val.strip()
    return lv


def _lv_find(lv, *keywords):
    """Case-insensitive lookup in label→value dict."""
    for lbl, val in lv.items():
        lbl_l = lbl.lower()
        if all(k.lower() in lbl_l for k in keywords):
            if val:
                return val
    return None


def parse_receipt_pdf(file_obj):
    """
    Parse a Railway Receipt Details PDF.

    Returns a dict with:
      date_of_receipt, receive_note_no, serial_number,
      item_desc, challan_no, quantity, unit,
      loa_number, contract_agreement, parse_warnings
    """
    result = {}
    warnings = []

    with pdfplumber.open(file_obj) as pdf:
        lv = _table_label_values(pdf)
        text = ''
        for page in pdf.pages:
            text += (page.extract_text() or '') + '\n'

    text = re.sub(r'\r\n?', '\n', text)

    # ── helpers ────────────────────────────────────────────────────────────────

    def get(text_pattern, flags=re.IGNORECASE, group=1):
        m = re.search(text_pattern, text, flags)
        return m.group(group).strip() if m else None

    def from_lv_or_text(lv_keys, text_pattern, flags=re.IGNORECASE):
        val = _lv_find(lv, *lv_keys)
        if not val:
            val = get(text_pattern, flags)
        return val

    # ── Date of Receipt ────────────────────────────────────────────────────────
    val = from_lv_or_text(
        ['date of receipt'],
        r'Date\s+of\s+Receipt\s+(\d{1,2}[-/]\d{1,2}[-/]\d{4})'
    )
    if val:
        result['date_of_receipt'] = _parse_date(val)
    else:
        warnings.append('Date of Receipt not found')

    # ── DMTR No. (Receive Note Number) ─────────────────────────────────────────
    val = from_lv_or_text(
        ['dmtr'],
        r'DMTR\s+No\.?\s+(\S+)'
    )
    if val:
        result['receive_note_no'] = val.strip()
    else:
        warnings.append('DMTR No. not found')

    # ── PO/Contract Item Sl. No. ───────────────────────────────────────────────
    val = from_lv_or_text(
        ['contract item sl', 'item sl'],
        r'PO/Contract\s+Item\s+Sl\.?\s*No\.?\s+(\S+)'
    )
    if val:
        # Trim "PL No./Item Code ..." if accidentally merged into this cell
        val = re.split(r'\s+PL\s+No', val, flags=re.IGNORECASE)[0]
        result['serial_number'] = _clean_sno(val)
    else:
        warnings.append('PO/Contract Item Sl. No. not found')

    # ── Description of Item ────────────────────────────────────────────────────
    val = _lv_find(lv, 'description of item')
    if not val:
        # Text extraction: grab from label until the next known section header
        m = re.search(
            r'Description of Item\s+(.*?)(?=\n(?:Item.s Qty|PO/Contract Unit|Delivery Period|Warranty|Payment Terms))',
            text, re.DOTALL | re.IGNORECASE
        )
        if m:
            val = m.group(1)
        else:
            m = re.search(r'Description of Item\s+(.+)', text, re.IGNORECASE)
            val = m.group(1) if m else None
    if val:
        result['item_desc'] = _clean_desc(val)
    else:
        warnings.append('Description of Item not found')

    # ── Challan No. & Date ─────────────────────────────────────────────────────
    # Prefer table value; avoid picking up "Invoice No.& Date" by excluding that key
    val = None
    for lbl, v in lv.items():
        if 'challan' in lbl.lower() and 'invoice' not in lbl.lower() and v:
            val = v
            break
    if not val:
        m = re.search(
            r'Challan\s+No\.?\s*&?\s*Date\s+(.*?)(?=Invoice No|IC No|\n)',
            text, re.IGNORECASE
        )
        if m:
            val = m.group(1).strip()
    if val:
        # Strip any trailing invoice info accidentally captured
        val = re.split(r'\s+Invoice', val, flags=re.IGNORECASE)[0].strip()
        result['challan_no'] = val
    else:
        warnings.append('Challan No. not found')

    # ── Qty. Accepted ──────────────────────────────────────────────────────────
    val = _lv_find(lv, 'qty', 'accepted')
    if not val:
        m = re.search(r'Qty\.?\s+Accepted\s+([\d.]+)\s+(\w+)', text, re.IGNORECASE)
        if m:
            val = f"{m.group(1)} {m.group(2)}"
    if val:
        qm = re.match(r'([\d.]+)\s+(\w+)', str(val).strip())
        if qm:
            try:
                result['quantity'] = float(qm.group(1))
                result['unit'] = qm.group(2)
            except ValueError:
                warnings.append(f'Could not parse quantity from: {val}')
        else:
            warnings.append(f'Qty. Accepted format unrecognised: {val}')
    else:
        warnings.append('Qty. Accepted not found')

    # ── LOA Number ────────────────────────────────────────────────────────────
    val = _lv_find(lv, 'loa') or _lv_find(lv, 'po no') or _lv_find(lv, 'po/loa')
    if not val:
        m = re.search(r'(?:LOA|PO)\s*No\.?\s*[:\s]\s*(\S+)', text, re.IGNORECASE)
        if m:
            val = m.group(1).strip()
    if val:
        result['loa_number'] = val.strip()

    # ── Contract Agreement Number ──────────────────────────────────────────────
    val = (_lv_find(lv, 'contract', 'agreement')
           or _lv_find(lv, 'agreement no')
           or _lv_find(lv, 'ca no'))
    if not val:
        m = re.search(
            r'(?:Contract\s+Agreement|Agreement)\s*No\.?\s*[:\s]\s*(\S+)',
            text, re.IGNORECASE
        )
        if m:
            val = m.group(1).strip()
    if val:
        result['contract_agreement'] = val.strip()

    result['parse_warnings'] = warnings
    return result
