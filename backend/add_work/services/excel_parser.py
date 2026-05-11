import pandas as pd
from works.models import Work, WorkItem


_HEADER_KEYWORDS = ('sch', 'serial', 's.no', 'item desc', 'description', 'qty', 'quantity', 'catagory', 'category')

# WorkItem fields that Excel may update (never touch supply/execution quantities or entries)
_UPDATABLE_FIELDS = (
    'category', 'item_desc', 'qty', 'unit', 'unit_rate_rs', 'unit_rate_below',
    'total_amount', 'inspection_agency',
)


def _find_header_row(df, search_limit=20):
    for i in range(min(search_limit, len(df))):
        cells = ' '.join(str(v).strip().lower() for v in df.iloc[i, :7].fillna(''))
        if any(kw in cells for kw in _HEADER_KEYWORDS):
            return i
    return None


def _meta_by_label(df, *labels, col=1, search_limit=20):
    for label in labels:
        lbl = label.lower()
        for i in range(min(search_limit, len(df))):
            cell = str(df.iloc[i, 0]).strip().lower()
            if lbl in cell:
                try:
                    val = df.iloc[i, col]
                    return str(val).strip() if not pd.isna(val) else ''
                except IndexError:
                    return ''
    return ''


def _safe_float(val):
    try:
        return float(val) if not pd.isna(val) else 0.0
    except Exception:
        return 0.0


def _clean_str(val):
    if pd.isna(val):
        return ''
    s = str(val).strip()
    try:
        f = float(s)
        if f == int(f):
            return str(int(f))
    except (ValueError, TypeError):
        pass
    return s


def _is_blank(val):
    return pd.isna(val) or str(val).strip() == ''


def _pad_loa(raw):
    """Normalise LOA to 14 digits — Excel strips leading zeros from numeric cells."""
    s = str(raw or '').strip()
    if not s:
        return s
    # Drop any decimal point Excel appends (e.g. "890160138264.0")
    if '.' in s:
        try:
            s = str(int(float(s)))
        except (ValueError, TypeError):
            pass
    if s.isdigit() and len(s) < 14:
        s = s.zfill(14)
    return s


_CATEGORY_MAP = {
    # New short codes
    'si': 'supply_installation',
    'ss': 'supply',
    'ee': 'execution',
    # Legacy long forms (keep for backward compat)
    'supply & installation': 'supply_installation',
    'supply and installation': 'supply_installation',
    's&i': 'supply_installation',
    's+i': 'supply_installation',
    'supply installation': 'supply_installation',
    'supply': 'supply',
    'execution': 'execution',
}

def _normalize_category(raw):
    if not raw:
        return ''
    key = raw.strip().lower()
    return _CATEGORY_MAP.get(key, key)


def _parse_two_sheet(xf):
    """Parse new two-tab format: sheet 0 = details, sheet 1 = items with Category column."""
    df_meta = xf.parse(sheet_name=0, header=None)

    loa_number         = _pad_loa(_meta_by_label(df_meta, 'loa'))
    tender_number      = _meta_by_label(df_meta, 'tender')
    date               = _meta_by_label(df_meta, 'date of loa', 'date')
    contract_agreement = _meta_by_label(df_meta, 'contract agreement', 'agreement')
    name_of_work       = _meta_by_label(df_meta, 'name of work', 'work')
    contractor_name    = _meta_by_label(df_meta, 'contractor name', 'contractor')
    contractor_address = _meta_by_label(df_meta, 'address')
    completion_date    = _meta_by_label(df_meta, 'completion', 'date of completion')
    consignee          = _meta_by_label(df_meta, 'consignee')
    hrms_id            = _meta_by_label(df_meta, 'hrms')

    df_items_raw = xf.parse(sheet_name=1, header=None)
    header_row = _find_header_row(df_items_raw)
    if header_row is None:
        raise ValueError("Could not find column header row in items sheet. Check the format.")

    df_items = xf.parse(sheet_name=1, header=None, skiprows=header_row + 1)

    # New column layout (0-indexed):
    # 0:Sch  1:S.No  2:Category  3:Item Desc  4:Item Qty  5:Qty Unit
    # 6:Unit Rate  7:8.20% above  8:Total Amount  9:Inspection
    sheet_items = []
    for _, row in df_items.iterrows():
        if _is_blank(row.iloc[1]) and _is_blank(row.iloc[3] if len(row) > 3 else None):
            continue
        category = _normalize_category(_clean_str(row.iloc[2]) if len(row) > 2 else '')
        agency   = _clean_str(row.iloc[9]) if len(row) > 9 else ''
        sheet_items.append({
            'schedule':          _clean_str(row.iloc[0]),
            'serial_number':     _clean_str(row.iloc[1]),
            'category':          category,
            'item_desc':         str(row.iloc[3]).strip() if len(row) > 3 and not _is_blank(row.iloc[3]) else '',
            'qty':               _safe_float(row.iloc[4]) if len(row) > 4 else 0.0,
            'unit':              str(row.iloc[5]).strip() if len(row) > 5 and not _is_blank(row.iloc[5]) else '',
            'unit_rate_rs':      _safe_float(row.iloc[6]) if len(row) > 6 else 0.0,
            'unit_rate_below':   _safe_float(row.iloc[7]) if len(row) > 7 else 0.0,
            'total_amount':      _safe_float(row.iloc[8]) if len(row) > 8 else 0.0,
            'inspection_agency': agency,
        })

    return loa_number, tender_number, date, contract_agreement, name_of_work, \
           contractor_name, contractor_address, completion_date, consignee, hrms_id, sheet_items


def _parse_single_sheet(xf):
    """Parse old single-sheet format (metadata + items on same sheet, no Category column)."""
    df = xf.parse(sheet_name=0, header=None)

    loa_number         = _pad_loa(_meta_by_label(df, 'loa'))
    tender_number      = _meta_by_label(df, 'tender')
    date               = _meta_by_label(df, 'date of loa', 'date')
    contract_agreement = _meta_by_label(df, 'contract agreement', 'agreement')
    name_of_work       = _meta_by_label(df, 'name of work', 'work')
    contractor_name    = _meta_by_label(df, 'contractor name', 'contractor')
    contractor_address = _meta_by_label(df, 'address')
    completion_date    = _meta_by_label(df, 'completion', 'date of completion')
    consignee          = _meta_by_label(df, 'consignee')
    hrms_id            = _meta_by_label(df, 'hrms')

    header_row = _find_header_row(df)
    if header_row is None:
        raise ValueError("Could not find the column header row in the sheet. Check the format.")

    df_items = xf.parse(sheet_name=0, header=None, skiprows=header_row + 1)

    # Old column layout: 0:Sch  1:S.No  2:Item Desc  3:Qty  4:Unit  5:Rate  6:8.20%  7:Total  8:Inspection
    sheet_items = []
    for _, row in df_items.iterrows():
        if _is_blank(row.iloc[1]) and _is_blank(row.iloc[2]):
            continue
        agency = _clean_str(row.iloc[8]) if len(row) > 8 else ''
        sheet_items.append({
            'schedule':          _clean_str(row.iloc[0]),
            'serial_number':     _clean_str(row.iloc[1]),
            'category':          '',
            'item_desc':         str(row.iloc[2]).strip() if not _is_blank(row.iloc[2]) else '',
            'qty':               _safe_float(row.iloc[3]),
            'unit':              str(row.iloc[4]).strip() if not _is_blank(row.iloc[4]) else '',
            'unit_rate_rs':      _safe_float(row.iloc[5]),
            'unit_rate_below':   _safe_float(row.iloc[6]),
            'total_amount':      _safe_float(row.iloc[7]),
            'inspection_agency': agency,
        })

    return loa_number, tender_number, date, contract_agreement, name_of_work, \
           contractor_name, contractor_address, completion_date, consignee, hrms_id, sheet_items


def parse_and_save_work_excel(file_path):
    xf = pd.ExcelFile(file_path)

    if len(xf.sheet_names) >= 2:
        result = _parse_two_sheet(xf)
    else:
        result = _parse_single_sheet(xf)

    (loa_number, tender_number, date, contract_agreement, name_of_work,
     contractor_name, contractor_address, completion_date, consignee, hrms_id,
     sheet_items) = result

    # ── Upsert: create new work OR update existing ────────────────────────────
    # Match padded OR stripped form — works saved before this fix may lack leading zeros.
    existing_work = None
    if loa_number:
        candidates = {loa_number, loa_number.lstrip('0')}
        existing_work = Work.objects.filter(loa_number__in=candidates).first()

    if existing_work is None:
        work = Work.objects.create(
            loa_number=loa_number,
            tender_number=tender_number,
            date=date,
            contract_agreement=contract_agreement,
            name_of_work=name_of_work,
            contractor_name=contractor_name,
            contractor_address=contractor_address,
            date_of_completion=completion_date,
            consignee=consignee,
            hrms_id=hrms_id,
        )
        for item in sheet_items:
            WorkItem.objects.create(work=work, **item)
        return {'status': 'created', 'items': len(sheet_items)}

    # ── UPDATE ────────────────────────────────────────────────────────────────
    changes = 0

    meta_map = {
        'tender_number': tender_number,
        'date': date,
        'contract_agreement': contract_agreement,
        'name_of_work': name_of_work,
        'contractor_name': contractor_name,
        'contractor_address': contractor_address,
        'date_of_completion': completion_date,
        'consignee': consignee,
        'hrms_id': hrms_id,
    }
    work_dirty = False
    for field, new_val in meta_map.items():
        if str(getattr(existing_work, field) or '').strip() != str(new_val or '').strip():
            setattr(existing_work, field, new_val)
            work_dirty = True
            changes += 1
    if work_dirty:
        existing_work.save()

    existing_items = {
        (i.schedule or '', i.serial_number or ''): i
        for i in existing_work.items.all()
    }

    for item_data in sheet_items:
        key = (item_data['schedule'], item_data['serial_number'])
        existing_item = existing_items.get(key)

        if existing_item is None:
            WorkItem.objects.create(work=existing_work, **item_data)
            changes += 1
        else:
            item_dirty = False
            for field in _UPDATABLE_FIELDS:
                old_val = getattr(existing_item, field)
                new_val = item_data[field]
                if isinstance(new_val, float):
                    old_cmp = float(old_val) if old_val is not None else 0.0
                    if abs(old_cmp - new_val) > 1e-9:
                        setattr(existing_item, field, new_val)
                        item_dirty = True
                else:
                    if str(old_val or '').strip() != str(new_val or '').strip():
                        setattr(existing_item, field, new_val)
                        item_dirty = True
            if item_dirty:
                existing_item.save(update_fields=list(_UPDATABLE_FIELDS))
                changes += 1

    if changes == 0:
        return {'status': 'no_changes', 'items': len(sheet_items)}

    return {'status': 'updated', 'items': len(sheet_items), 'changes': changes}
