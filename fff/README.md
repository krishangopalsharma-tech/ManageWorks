# LOA 38264 · Marvel Pvt. Ltd. · Telecom Progress Dashboard

Single-page interactive dashboard for the Marvel Pvt. Ltd. railway telecom contract (LOA No. 38264, 17.53 % below schedule). Built from the source workbook **`04_Tele_Marvel_38264_office.xlsx`**.

## What's in this package

```
dashboard.html      The dashboard — open in any modern browser.
data.json           Cleaned data payload (also embedded inside dashboard.html).
build_data.py       Regenerates data.json + re-injects it into dashboard.html.
README.md           This file.
```

`dashboard.html` is a **single self-contained file**. Loads ECharts v5 from a public CDN (`cdn.jsdelivr.net`) on first open — after that, it works fully interactively.

## How to open

1. Double-click `dashboard.html` (opens in your default browser).
2. Works offline **after** the first open (browser caches the ECharts library).

## Reading the dashboard

**KPI strip (top, left-to-right):**

1. **Total Contract Value** — sum of `Qty × Unit Rate below (17.53)` across all 160 items.
2. **Value Earned to Date** — sum of the `Progress amount` column.
3. **Overall Financial Progress** — `Earned / Contract`, value-weighted.
4. **Material Supply Progress** — Sch A earned / Sch A contract (value-weighted).
5. **Execution Progress** — Sch B earned / Sch B contract (value-weighted).
6. **Pending Value** — Contract − Earned.

All monetary numbers use the **rebate-adjusted rate (Column 8, `Unit Rate below (17.53)`)**, never the schedule rate.

**Cross-filtering**

Every filter chip, every search box, and clicks on several charts (inspection agency, status donut, brand-wise bar, unit treemap) cross-filter every other chart and the line-item table. The `Reset filters` button clears everything.

---

## Important: three different baseline metrics in the source sheet

Row 1 of the source file contains three percentages (61.13 %, 23.12 %, 30.27 %). **These are not three views of the same number** — the sheet uses three different formulas, two of which don't mean what their labels suggest. All three were reconciled to within 0.004 pp before building.

| Sheet label | Cell & formula | Value | What it actually measures |
|---|---|---|---|
| Material Supply | `D1 = L109/I109` | 61.13 % | Sch A earned ÷ Sch A contract (value-weighted). ✓ Matches this dashboard's Supply KPI. |
| "Over all progress" *(the 23.12 cell)* | `J1 = AVERAGE(K3:K163)` | 23.12 % | Simple unweighted average of per-item `Progress` ratios across all 160 items. A line-count metric — small and large items count equally. |
| Financial | `M1 = (S164+U164)/(I109+I164)` | 30.27 % | (Sum of MB01 + MB02 values on Sch A supply rows) ÷ total A+B contract. Represents partial-billing MB stages (80 %/90 % release factors baked into `=R*H*0.8` and `=T*H*0.9`), not final earned value. |

**The dashboard shows the value-weighted metrics you asked for in the brief**, not the file's three numbers — because the file's "Execution 23.12 %" dilutes Sch B's real weighted progress (7.48 %) by averaging in mostly-complete Sch A items, and the "Financial 30.27 %" reflects retention-stage MB billing on supply items only, not total earned.

The three file numbers are printed in the dashboard footer for transparency.

### How weighted % is computed in this dashboard

- **Supply %** = `Σ(ProgressAmount_i for i in Sch A) / Σ(TotalAmount_i for i in Sch A)`
- **Execution %** = `Σ(ProgressAmount_i for i in Sch B) / Σ(TotalAmount_i for i in Sch B)`
- **Overall Financial %** = `Σ(ProgressAmount_i for all i) / Σ(TotalAmount_i for all i)`

`TotalAmount` uses the **below-rebate rate** (Column 8) — the rate at which payments are actually made under this contract.

---

## Data-cleaning rules applied

Performed in `build_data.py` (traceable, reproducible):

1. **Header** — row 2 is the header; row 1 (summary percentages) and rows 165-169 (grand total block) are skipped.
2. **Schedule split** — rows 3-108 are Sch A (106 items); rows 110-163 are Sch B (54 items). Rows 109 and 164 (per-schedule subtotals) are dropped.
3. **Blank progress → 0** per the brief.
4. **Inspection normalisation**
   - `consignee` (lower-case) → `Consignee`
   - `RITES (Amendment required from RITES to Consignee)` → `RITES` (pre-amendment agency)
   - Everything else kept as-is
5. **Brand extraction** from `Technical specification` (27 distinct brands after cleanup):
   - `webfill` → `Webfil`, `puncom` → `Puncom` (case variants unified)
   - Multi-brand strings (`"Havells, Torrent, Gloster, Bharat cables, Avocab, Polycab, Finolex or, Anchor"`) → first brand becomes the primary (`Havells` here)
   - Comment-like strings (`???`, bare URLs) → `Unspecified`
6. **Challan dates** parsed from the challan string using regex `\d{1,2}[-./]\d{1,2}[-./]\d{2,4}`. 36 items have dated challans (Oct 2025 – Mar 2026).
7. **Value bands** auto-assigned: `<₹1L`, `₹1L–10L`, `₹10L–1Cr`, `>₹1Cr`.
8. **Status bucket** — `Completed` ≥ 99 %, `In Progress` > 0 % and < 99 %, `Not Started` = 0 %.

---

## How to refresh if the source Excel changes

```bash
# 1. Overwrite the source workbook in the same path used by the script:
#    /mnt/user-data/uploads/04_Tele_Marvel_38264_office.xlsx
#    (or edit the SRC constant at the top of build_data.py)

# 2. Regenerate data.json:
python3 build_data.py

# 3. Re-inject the fresh data into dashboard.html.
#    The reinjection is just string-replacement of the <script id="dashData"> block.
#    If you prefer a one-liner, run:
python3 -c "
import json, re
d = json.dumps(json.load(open('data.json')), ensure_ascii=False, separators=(',',':'), allow_nan=False)
d = d.replace('</script', '<\\/script').replace('<!--', '<\\!--')
html = open('dashboard.html',encoding='utf-8').read()
html = re.sub(r'<script id=\"dashData\"[^>]*>.*?</script>',
              f'<script id=\"dashData\" type=\"application/json\">{d}</script>',
              html, count=1, flags=re.DOTALL)
open('dashboard.html','w',encoding='utf-8').write(html)
print('Refreshed.')
"
```

The script expects the sheet name `LOA Details` and the column layout defined on row 2 of the source (21 columns, MB01/MB02 split across qty+value). If the sheet structure changes (new columns inserted, renamed headers), the `df.columns = [...]` block near the top of `build_data.py` must be updated accordingly.

---

## Baseline reconciliation (for audit)

Reproducible check at script start; script refuses to emit bad data:

```
File reconciliation -> Supply 61.13 (exp 61.13)
                      AvgProg 23.12 (exp 23.12)
                      MB/Total 30.27 (exp 30.27)
```

Deltas all < 0.005 pp.

---

## Design notes

- **Colours** — Sch A is deep teal (`#1D5F5E`), Sch B is warm terracotta (`#C17841`). Both are used consistently across every chart (gauge, waterfall, top-10 bars, inspection stack, brand stack, treemap, scatter, timeline, Pareto, cadence bars). Red (`#B63A2E`) appears only on the Pareto 80 % marker and the "Pending Value" KPI accent — reserved for flags.
- **Typography** — single family (Manrope), three sizes (28/13/11 px), tabular numerals everywhere numbers appear.
- **Empty-state handling** — if a filter combination returns zero rows, each chart displays a neutral "No data" centred message and the insights panel flips to a guidance line. No chart errors out.
- **Executive brevity** — each chart has a one-line title, a one-line subtitle naming the unit, and a tooltip with the exact value. No legends repeat what titles already say.

## Known limitations

- The MB billing-velocity ETA in the insights panel is a naive linear projection (total remaining ÷ average monthly billing over months that have had any challan activity). It's intended as a first-pass indicator, not a planning commitment.
- The "supply vs execution alignment" scatter plots per-item progress against contract value on a log axis rather than pairing Sch A supply items 1:1 with Sch B execution items — because the source BOQ doesn't have a reliable supply-to-execution mapping (the two schedules have different SNo namespaces and different item descriptions). The chart still makes the core point: dots clustered in the top-left of the plot area (high value, low progress) are the items where money is tied up.
