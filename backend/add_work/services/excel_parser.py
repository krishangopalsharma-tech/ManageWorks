import pandas as pd
from works.models import Work, WorkItem


def parse_and_save_work_excel(file_path):
    df = pd.read_excel(file_path, header=None)

    def safe_val(row, col):
        try:
            val = df.iloc[row, col]
            return str(val).strip() if not pd.isna(val) else ""
        except IndexError:
            return ""

    loa_number = safe_val(0, 1)
    tender_number = safe_val(1, 1)
    date = safe_val(2, 1)
    contract_agreement = safe_val(3, 1)
    contractor_name = safe_val(4, 1)
    contractor_address = safe_val(5, 1)
    completion_date = safe_val(6, 1)
    consignee = safe_val(7, 1)

    if loa_number and Work.objects.filter(loa_number=loa_number).exists():
        raise ValueError(f"A Work document with LOA '{loa_number}' has already been uploaded.")

    work = Work.objects.create(
        loa_number=loa_number,
        tender_number=tender_number,
        date=date,
        contract_agreement=contract_agreement,
        contractor_name=contractor_name,
        contractor_address=contractor_address,
        date_of_completion=completion_date,
        consignee=consignee,
    )

    df_items = pd.read_excel(file_path, skiprows=7)

    def safe_float(val):
        try:
            return float(val) if not pd.isna(val) else 0.0
        except Exception:
            return 0.0

    items_created = 0
    for _, row in df_items.iterrows():
        if pd.isna(row.iloc[0]) and pd.isna(row.iloc[2]) and pd.isna(row.iloc[3]):
            continue
        WorkItem.objects.create(
            work=work,
            schedule=str(row.iloc[0]) if not pd.isna(row.iloc[0]) else "",
            serial_number=str(row.iloc[1]) if not pd.isna(row.iloc[1]) else "",
            item_desc=str(row.iloc[2]) if not pd.isna(row.iloc[2]) else "",
            qty=safe_float(row.iloc[3]),
            unit=str(row.iloc[4]) if not pd.isna(row.iloc[4]) else "",
            unit_rate_rs=safe_float(row.iloc[5]),
            unit_rate_below=safe_float(row.iloc[6]),
            total_amount=safe_float(row.iloc[7]),
        )
        items_created += 1

    return items_created
