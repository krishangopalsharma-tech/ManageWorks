import pandas as pd
from works.models import Work, WorkItem


_HEADER_KEYWORDS = ('sch', 'serial', 's.no', 'item desc', 'description', 'qty', 'quantity')


def _find_header_row(df, search_limit=20):
    for i in range(min(search_limit, len(df))):
        cells = ' '.join(str(v).strip().lower() for v in df.iloc[i, :6].fillna(''))
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


def parse_and_save_work_excel(file_path):
    df = pd.read_excel(file_path, header=None)

    loa_number         = _meta_by_label(df, 'loa')
    tender_number      = _meta_by_label(df, 'tender')
    date               = _meta_by_label(df, 'date of loa', 'date')
    contract_agreement = _meta_by_label(df, 'contract agreement', 'agreement')
    name_of_work       = _meta_by_label(df, 'name of work', 'work')
    contractor_name    = _meta_by_label(df, 'contractor name', 'contractor')
    contractor_address = _meta_by_label(df, 'address')
    completion_date    = _meta_by_label(df, 'completion', 'date of completion')
    consignee          = _meta_by_label(df, 'consignee')
    hrms_id            = _meta_by_label(df, 'hrms')

    if loa_number and Work.objects.filter(loa_number=loa_number).exists():
        raise ValueError(f"A Work document with LOA '{loa_number}' has already been uploaded.")

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

    header_row = _find_header_row(df)
    if header_row is None:
        return 0

    df_items = pd.read_excel(file_path, header=None, skiprows=header_row + 1)

    def safe_float(val):
        try:
            return float(val) if not pd.isna(val) else 0.0
        except Exception:
            return 0.0

    def clean_str(val):
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

    def is_blank(val):
        return pd.isna(val) or str(val).strip() == ''

    items_created = 0
    for _, row in df_items.iterrows():
        if is_blank(row.iloc[0]) and is_blank(row.iloc[2]) and is_blank(row.iloc[3]):
            continue

        inspection_agency = ''
        if len(row) > 8:
            inspection_agency = clean_str(row.iloc[8])

        WorkItem.objects.create(
            work=work,
            schedule=clean_str(row.iloc[0]),
            serial_number=clean_str(row.iloc[1]),
            item_desc=str(row.iloc[2]).strip() if not is_blank(row.iloc[2]) else '',
            qty=safe_float(row.iloc[3]),
            unit=str(row.iloc[4]).strip() if not is_blank(row.iloc[4]) else '',
            unit_rate_rs=safe_float(row.iloc[5]),
            unit_rate_below=safe_float(row.iloc[6]),
            total_amount=safe_float(row.iloc[7]),
            inspection_agency=inspection_agency,
        )
        items_created += 1

    return items_created
