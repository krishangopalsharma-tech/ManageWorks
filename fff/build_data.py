"""Build the clean JSON payload for the Marvel LOA-38264 dashboard."""
import pandas as pd
import numpy as np
import json
import re
from datetime import datetime
from collections import defaultdict

SRC = '/mnt/user-data/uploads/04_Tele_Marvel_38264_office.xlsx'

df = pd.read_excel(SRC, sheet_name='LOA Details', header=1)
df.columns = ['Sch','SNo','ItemDesc','TechSpec','Qty','Unit','UnitRate','UnitRateBelow',
              'TotalAmount','SuppliedExecQty','Progress','ProgressAmount','ChallanNo','UDMEntry',
              'Remark','Inspection','Remaining','MB01_Qty','MB01_Value','MB02_Qty','MB02_Value']
df = df[df['Sch'].isin(['A','B'])].copy().reset_index(drop=True)

num_cols = ['Qty','UnitRate','UnitRateBelow','TotalAmount','SuppliedExecQty','Progress',
            'ProgressAmount','Remaining','MB01_Qty','MB01_Value','MB02_Qty','MB02_Value']
for c in num_cols:
    df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0)

# --- Clean text fields ---
def clean_str(x):
    if pd.isna(x): return ''
    return str(x).strip()

for c in ['ItemDesc','TechSpec','Unit','ChallanNo','UDMEntry','Remark','Inspection']:
    df[c] = df[c].apply(clean_str)

# Normalise Unit (e.g. "Man- Days" -> "Man-Days")
df['Unit'] = df['Unit'].str.replace(r'\s*-\s*', '-', regex=True).str.strip()

# --- Inspection normalisation ---
def norm_inspection(s):
    s = (s or '').strip()
    if not s: return ''
    low = s.lower()
    if 'rdso' in low: return 'RDSO'
    if 'rites' in low and 'amendment' in low: return 'RITES'  # amendment line -> RITES (pre-amendment)
    if 'rites' in low: return 'RITES'
    if 'consignee' in low: return 'Consignee'
    return s
df['InspectionClean'] = df['Inspection'].apply(norm_inspection)

# --- Brand normalisation ---
BRAND_MAP = {
    'webfil':'Webfil','webfill':'Webfil',
    'puncom':'Puncom',
    'jbl':'JBL',
    'dinstar':'Dinstar',
    'shure':'Shure',
    'zyxel':'Zyxel',
    'yamaha':'Yamaha',
    'crown':'Crown',
    'godrej':'Godrej',
    'rishabh':'Rishabh',
    'd-link':'D-Link',
    'commscope':'CommScope',
    'r&m':'R&M',
    'molex':'Molex',
    'finolex':'Finolex',
    'havells':'Havells',
    'polycab':'Polycab',
    'anchor':'Anchor',
    'torrent':'Torrent',
    'gloster':'Gloster',
    'avocab':'Avocab',
    'bharat cables':'Bharat Cables',
    'yihua':'YIHUA',
    'statcon':'Statcon Energia',
    'apc':'APC',
    'dasscom':'Dasscom',
    'beetal':'Beetal',
    'tejas':'Tejas',
    'sumitomo':'Sumitomo',
    'sony':'Sony','samsung':'Samsung',
    'mukand':'Mukand','narayani':'Narayani','dura-line':'Dura-Line',
    'saraswat':'Saraswat',
    'dell':'Dell','hp':'HP',
}
def brand_of(s):
    s = (s or '').strip()
    if not s: return 'Unspecified'
    if s in ('???',): return 'Unspecified'
    if s.lower().startswith('http'): return 'Unspecified'
    low = s.lower()
    for k, v in BRAND_MAP.items():
        if k in low:
            return v
    # Fall back: title case first word-ish token
    tok = re.split(r'[,\s/]+', s.strip())[0]
    return tok[:1].upper() + tok[1:] if tok else 'Unspecified'
df['Brand'] = df['TechSpec'].apply(brand_of)

# --- Status bucket (progress ratio based) ---
def status_bucket(p):
    if p >= 0.99: return 'Completed'
    if p > 0:     return 'In Progress'
    return 'Not Started'
df['StatusBucket'] = df['Progress'].apply(status_bucket)

# --- Parse challan date (format 'MEEPL/25-26/ADI Tele04/011 dt.28-11-2025') ---
date_re = re.compile(r'(\d{1,2})[-./](\d{1,2})[-./](\d{2,4})')
def parse_challan_date(s):
    if not s: return None
    m = date_re.search(s)
    if not m: return None
    d, mo, y = m.groups()
    y = int(y); 
    if y < 100: y += 2000
    try:
        dt = datetime(y, int(mo), int(d))
        return dt.isoformat()[:10]
    except:
        return None
df['ChallanDate'] = df['ChallanNo'].apply(parse_challan_date)

# --- Value-band bucket ---
def value_band(amt):
    if amt < 100000: return '<₹1L'
    if amt < 1000000: return '₹1L–10L'
    if amt < 10000000: return '₹10L–1Cr'
    return '>₹1Cr'
df['ValueBand'] = df['TotalAmount'].apply(value_band)

# --- Summary totals ---
a = df[df['Sch']=='A']; b = df[df['Sch']=='B']
contract_total = df['TotalAmount'].sum()
earned_total = df['ProgressAmount'].sum()
a_contract = a['TotalAmount'].sum(); a_earned = a['ProgressAmount'].sum()
b_contract = b['TotalAmount'].sum(); b_earned = b['ProgressAmount'].sum()

# File-formula baselines (for reconciliation block)
ms_file = a_earned/a_contract*100
exec_file_avg = df['Progress'].mean()*100
# Financial = (MB01+MB02 summed across rows 3..163) / (total contract)
fin_file = (df['MB01_Value'].sum()+df['MB02_Value'].sum()) / contract_total * 100

print(f"File reconciliation -> Supply {ms_file:.2f} (exp 61.13) | AvgProg {exec_file_avg:.2f} (exp 23.12) | MB/Total {fin_file:.2f} (exp 30.27)")

# --- Build challan timeline (monthly) ---
timeline = defaultdict(lambda: {'count': 0, 'value': 0.0})
for _, r in df.iterrows():
    cd = r['ChallanDate']
    if isinstance(cd, str) and len(cd) >= 7:
        ym = cd[:7]  # 'YYYY-MM'
        timeline[ym]['count'] += 1
        # Use MB01+MB02 values as billed amount for this challan
        timeline[ym]['value'] += float(r['MB01_Value'] + r['MB02_Value'])

timeline_sorted = sorted(timeline.items())
timeline_list = [{'month': m, 'count': v['count'], 'value': v['value']} for m, v in timeline_sorted]

# --- Items list ---
def to_native(v):
    """Convert NaN/NaT/numpy scalars to JSON-safe natives."""
    if v is None: return None
    if isinstance(v, float):
        if np.isnan(v) or np.isinf(v): return None
        return v
    try:
        if pd.isna(v): return None
    except (TypeError, ValueError):
        pass
    return v

items = []
for idx, r in df.iterrows():
    items.append({
        'sch': r['Sch'],
        'sno': int(r['SNo']) if pd.notna(r['SNo']) else idx,
        'desc': r['ItemDesc'],
        'techSpec': r['TechSpec'],
        'brand': r['Brand'],
        'qty': float(r['Qty']),
        'unit': r['Unit'] or '—',
        'unitRate': float(r['UnitRate']),
        'unitRateBelow': float(r['UnitRateBelow']),
        'totalAmount': float(r['TotalAmount']),
        'suppliedQty': float(r['SuppliedExecQty']),
        'progress': float(r['Progress']),
        'progressAmount': float(r['ProgressAmount']),
        'challanNo': r['ChallanNo'],
        'challanDate': to_native(r['ChallanDate']),
        'udmEntry': r['UDMEntry'],
        'inspection': r['InspectionClean'],
        'inspectionRaw': r['Inspection'],
        'remaining': float(r['Remaining']),
        'mb01Qty': float(r['MB01_Qty']),
        'mb01Value': float(r['MB01_Value']),
        'mb02Qty': float(r['MB02_Qty']),
        'mb02Value': float(r['MB02_Value']),
        'pendingValue': float(r['TotalAmount'] - r['ProgressAmount']),
        'status': r['StatusBucket'],
        'valueBand': r['ValueBand'],
    })

# Distinct lists (for filter chips)
brands = sorted(set(i['brand'] for i in items))
units = sorted(set(i['unit'] for i in items))
inspections = sorted(set(i['inspection'] for i in items if i['inspection']))

payload = {
    'meta': {
        'loaNo': '38264',
        'contractor': 'Marvel Pvt. Ltd.',
        'work': 'Railway Telecom (LOA-38264)',
        'rebatePct': 17.53,
        'rateColumnUsed': 'Unit Rate below 17.53 (i.e. rebate-adjusted billing rate, Col 8)',
        'generatedOn': datetime.now().isoformat()[:19],
        'counts': {'schA': len(a), 'schB': len(b), 'total': len(df)},
        'totals': {
            'contract': float(contract_total),
            'earned': float(earned_total),
            'pending': float(contract_total - earned_total),
            'schA': {
                'contract': float(a_contract), 'earned': float(a_earned),
                'pct': float(a_earned/a_contract*100)
            },
            'schB': {
                'contract': float(b_contract), 'earned': float(b_earned),
                'pct': float(b_earned/b_contract*100)
            },
            'overallPct': float(earned_total/contract_total*100),
        },
        'fileBaseline': {
            'materialSupplyPct': round(ms_file, 2),
            'fileExecAvgProgressPct': round(exec_file_avg, 2),
            'fileFinancialMbRatioPct': round(fin_file, 2),
            'note': "File row 1 uses three different formulas: Material Supply = Sch-A earned/contract (value-weighted). 'Execution' in file = simple unweighted average of per-item progress ratios across all items. 'Financial' in file = (MB01+MB02 values on supply items) / total contract — represents retention-stage MB billing, not final earned."
        },
    },
    'items': items,
    'challanTimeline': timeline_list,
    'filters': {
        'brands': brands,
        'units': units,
        'inspections': inspections,
    }
}

with open('/home/claude/dash/data.json', 'w') as f:
    json.dump(payload, f, indent=2, ensure_ascii=False, allow_nan=False)
print(f"Wrote data.json — {len(items)} items, {len(timeline_list)} months of challan data")
print(f"Brands: {len(brands)} | Units: {len(units)} | Inspections: {inspections}")
