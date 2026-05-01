"""
PDF parser for IRWCMS-format Record Measurement (RM) MBs.

Extracts: MB number, agreement reference, date of measurement, and per-item
records with schedule, item_no, description, unit, quantity, total_to_date,
current_percentage.

Format characteristics handled:
- Header has both "MB No." and "Record Measurement No." lines
- Item rows can wrap descriptions across multiple lines
- Unit column wraps in PDF (e.g. "Runnin g Metre" -> "Running Metre")
- Item no may be zero-padded ("01") or not ("1")
- "Now to pay" line may have "=" or not
- Page breaks split item rows — headers stripped from non-first pages
"""

import re
import pdfplumber


_LBH_PATTERN = r'[\d.]+\s*x\s*[\d.]+\s*x\s*[\d.]+'

_UNIT_TOKEN = (
    r'(?:Metre|Lumpsu\s*m|Number\s*s|Number|Kilometr\s*e|'
    r'Runnin\s*g\s*Metre|Running\s*Metre|cum|Set|Man\s*-?\s*Days|ManDays)'
)

# Lines to strip from non-first pages so cross-page item descriptions aren't polluted.
_PAGE_HEADER_LINE_RES = [
    re.compile(r'^\s*MB\s*No\.', re.IGNORECASE),
    re.compile(r'^\s*Record\s+Measurement\s+No\.', re.IGNORECASE),
    re.compile(r'^\s*Reference\s+to\s+agreement', re.IGNORECASE),
    re.compile(r'^\s*Agency\s+By\s+which', re.IGNORECASE),
    re.compile(r'^\s*Date\s+of\s+(?:Measurement|commencement)', re.IGNORECASE),
    re.compile(r'^\s*Sl\.?\s*No\.?\s+Description', re.IGNORECASE),
    re.compile(r'^\s*S\.?\s*No\.?\s+Description', re.IGNORECASE),
    re.compile(r'^\s*IRWCMS\b', re.IGNORECASE),
    # Column-header continuation lines (L B H Content Nos. ...)
    re.compile(r'^\s*L\s+B\s+H\s+Content', re.IGNORECASE),
    re.compile(r'^\s*Rate\s+per\s+Unit', re.IGNORECASE),
]


def _strip_page_header_lines(page_text):
    """Remove known IRWCMS header/column-header lines from a non-first page."""
    lines = page_text.split('\n')
    cleaned = []
    for line in lines:
        if any(pat.match(line) for pat in _PAGE_HEADER_LINE_RES):
            continue
        cleaned.append(line)
    return '\n'.join(cleaned)


def _normalize_unit(unit):
    if not unit:
        return ''
    u = re.sub(r'\s+', ' ', unit.strip())
    fixes = {
        r'\bRunnin\s+g\b':    'Running',
        r'\bLumpsu\s+m\b':    'Lumpsum',
        r'\bNumber\s+s\b':    'Numbers',
        r'\bKilometr\s+e\b':  'Kilometre',
        r'\bMan-?\s+Days\b':  'Man-Days',
    }
    for pat, repl in fixes.items():
        u = re.sub(pat, repl, u, flags=re.IGNORECASE)
    return u.strip()


def _normalize_serial(s):
    s = str(s or '').strip()
    if not s:
        return ''
    if s.endswith('.0'):
        s = s[:-2]
    s = s.lstrip('0') or '0'
    return s


def _extract_text(file_obj):
    """Concat text from all pages; strip repeated page headers from pages 2+ so
    cross-page items (description continues on next page) parse correctly."""
    parts = []
    with pdfplumber.open(file_obj) as pdf:
        for i, page in enumerate(pdf.pages):
            txt = page.extract_text() or ''
            if i > 0:
                txt = _strip_page_header_lines(txt)
            parts.append(txt)
    return '\n'.join(parts)


def _parse_header(text):
    h = {}

    m = re.search(r'\bMB No\.\s*(\S[^\n]*)', text)
    if m:
        h['mb_no_parent'] = m.group(1).strip()

    m = re.search(r'Record Measurement No\.\s*(\S[^\n]*)', text)
    if m:
        h['mb_number'] = m.group(1).strip()

    m = re.search(r'Reference to agreement of work order\s*:\s*([^\n]+)', text)
    if m:
        ref = m.group(1).strip()
        d_match = re.search(r'(.+?)\s+Dated\s*:\s*(\S+)', ref)
        if d_match:
            h['agreement']    = d_match.group(1).strip()
            h['agreement_dt'] = d_match.group(2).strip()
        else:
            h['agreement'] = ref

    m = re.search(r'Agency By which work executed\s*:\s*([^\n]+)', text)
    if m:
        h['agency'] = m.group(1).strip()

    m = re.search(r'Date of Measurement\s*:\s*([^\n]+)', text)
    if m:
        h['date_of_measurement'] = m.group(1).strip()

    m = re.search(r'Date of commencement\s*:\s*([^\n]+)', text)
    if m:
        h['date_of_commencement'] = m.group(1).strip()

    return h


_ITEM_NO_RE = re.compile(r'Item No\.\s*:\s*(\d+)', re.IGNORECASE)


def _split_into_schedule_blocks(text):
    matches = list(re.finditer(r'\bSCHEDULE\s+([AB])\b', text))
    if not matches:
        return []

    blocks = []
    for i, m in enumerate(matches):
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        blocks.append((m.group(1).upper(), text[start:end]))
    return blocks


def _split_into_item_blocks(block_text):
    starts = [m.start() for m in _ITEM_NO_RE.finditer(block_text)]
    if not starts:
        return []
    items = []
    for i, s in enumerate(starts):
        e = starts[i + 1] if i + 1 < len(starts) else len(block_text)
        items.append(block_text[s:e])
    return items


_QTY_ROW_RE = re.compile(
    r'(' + _UNIT_TOKEN + r')'
    r'\s+' + _LBH_PATTERN +
    r'\s+[\d.]+'
    r'\s+([\d.]+)'
    r'\s+=\s+([\d.]+)',
    re.IGNORECASE,
)

_LBH_RE   = re.compile(_LBH_PATTERN)
_TOTAL_RE = re.compile(r'\bTotal\s+([\d.]+)', re.IGNORECASE)
_PAY_RE   = re.compile(r'Now to pay\s*=?\s*([\d.]+)\s*%', re.IGNORECASE)


def _split_description(block_text):
    m = _ITEM_NO_RE.search(block_text)
    if not m:
        return ''
    after = block_text[m.end():]

    lbh = _LBH_RE.search(after)
    end = lbh.start() if lbh else len(after)

    desc = after[:end]

    line_anchor = re.search(
        r'\n\s*(Supplied\s+by|Installed\s+by|Installation\s+done|'
        r'Execution\s+Done|Executed\s+by|executed\s+by|Exceccuted\s+by|'
        r'Supply\s+and\s+install)',
        desc, re.IGNORECASE
    )
    if line_anchor:
        desc = desc[:line_anchor.start()]

    desc = desc.strip().strip('"').strip("'")
    desc = re.sub(r'\s+', ' ', desc)
    return desc


def _parse_item_block(block_text, schedule):
    item = {'schedule': schedule}

    m = _ITEM_NO_RE.search(block_text)
    if not m:
        return None
    item['item_no']      = m.group(1)
    item['item_no_norm'] = _normalize_serial(m.group(1))

    item['description'] = _split_description(block_text)

    qm = _QTY_ROW_RE.search(block_text)
    if qm:
        item['unit']     = _normalize_unit(qm.group(1))
        item['quantity'] = float(qm.group(2))
    else:
        item['unit']     = ''
        item['quantity'] = 0.0

    tm = _TOTAL_RE.search(block_text)
    item['total_to_date'] = float(tm.group(1)) if tm else item.get('quantity', 0.0)

    pm = _PAY_RE.search(block_text)
    item['current_percentage'] = float(pm.group(1)) if pm else 0.0

    return item


def parse_rm_pdf(file_obj):
    """
    Parse an IRWCMS Record Measurement PDF.

    Returns dict:
      {
        'header': { mb_number, agreement, date_of_measurement, ... },
        'items': [
          { schedule, item_no, item_no_norm, description, unit,
            quantity, total_to_date, current_percentage }
        ],
        'raw_text_preview': '<first 500 chars for debugging>',
      }
    """
    text = _extract_text(file_obj)

    if not text.strip():
        return {
            'header': {},
            'items': [],
            'error': 'PDF has no text layer (scanned image?). Use a digitally generated PDF.',
        }

    header = _parse_header(text)
    items  = []

    for sch, block in _split_into_schedule_blocks(text):
        for ib in _split_into_item_blocks(block):
            item = _parse_item_block(ib, sch)
            if item and item.get('current_percentage', 0) > 0:
                items.append(item)

    return {
        'header': header,
        'items':  items,
        'raw_text_preview': text[:500],
    }
