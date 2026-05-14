import csv
import io
import urllib.request
from collections import defaultdict

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied

from site_gsheet_settings.models import SiteGSheet
from works.models import Work


def _is_admin(user):
    if not user.is_authenticated:
        return False
    if user.is_staff:
        return True
    profile = getattr(user, 'profile', None)
    return profile is not None and profile.role == 'admin'


def _fetch_input_tab(sheet_id):
    url = (
        f"https://docs.google.com/spreadsheets/d/{sheet_id}"
        f"/gviz/tq?tqx=out:csv&sheet=Input"
    )
    with urllib.request.urlopen(url, timeout=15) as r:
        return r.read().decode("utf-8")


def _parse_rows(csv_text):
    reader = csv.reader(io.StringIO(csv_text))
    rows = []
    for row in reader:
        if len(row) < 5:
            continue
        rows.append({
            "datetime":   row[0].strip(),
            "loa_number": row[1].strip(),
            "schedule":   row[2].strip(),
            "serial_no":  row[3].strip(),
            "item_desc":  row[4].strip(),
            "remark":     row[5].strip() if len(row) > 5 else "",
        })
    return rows


def _fetch_all_sheet_rows():
    """Returns (rows, sheet_errors)."""
    sheets = list(SiteGSheet.objects.filter(is_active=True))
    all_rows, errors = [], []
    for sheet in sheets:
        try:
            csv_text = _fetch_input_tab(sheet.sheet_id)
            rows = _parse_rows(csv_text)
            for r in rows:
                r["sheet_name"] = sheet.name
                r["sheet_id"]   = sheet.id
            all_rows.extend(rows)
        except Exception as e:
            errors.append({"sheet": sheet.name, "error": str(e)})
    return all_rows, errors


def _validate_entry(row, work, items_by_work):
    """Return list of warning strings for a single entry row."""
    warnings = []
    if not work:
        warnings.append("LOA number not found in system")
        return warnings
    work_items = items_by_work.get(work.id, {})
    schedules_in_work = {s for s, _ in work_items}
    sch = row["schedule"].lower()
    sn  = row["serial_no"].lower()
    if sch not in schedules_in_work:
        warnings.append(f"Schedule '{row['schedule']}' not found for this LOA")
    elif (sch, sn) not in work_items:
        warnings.append(f"Serial no '{row['serial_no']}' not found in schedule '{row['schedule']}'")
    return warnings


class SiteRegisterView(APIView):
    """
    Returns ALL works in the system.
    For each work, attaches matching sheet entries (by LOA number).
    """
    def get(self, request):
        if not request.user.is_authenticated:
            raise PermissionDenied("Authentication required.")

        # Admins see all works; consignees only see works assigned to them
        qs = Work.objects.prefetch_related("items").order_by("contractor_name")
        if not _is_admin(request.user):
            qs = qs.filter(hrms_id=request.user.username)

        works = list(qs)

        # Pre-build items lookup: { work_id: { (schedule.lower(), serial_no.lower()): item_dict } }
        items_by_work = defaultdict(dict)
        items_detail  = defaultdict(list)   # work_id → list of item dicts (for frontend)
        for w in works:
            for item in w.items.all():
                key = (
                    (item.schedule or "").strip().lower(),
                    (item.serial_number or "").strip().lower(),
                )
                items_by_work[w.id][key] = item
                items_detail[w.id].append({
                    "id":          item.id,
                    "schedule":    item.schedule,
                    "serial_no":   item.serial_number,
                    "item_desc":   item.item_desc,
                    "qty":         item.qty,
                    "unit":        item.unit,
                })

        works_by_loa = {w.loa_number: w for w in works if w.loa_number}

        # Fetch sheet rows
        all_rows, sheet_errors = _fetch_all_sheet_rows()

        # Index sheet rows by loa_number
        rows_by_loa = defaultdict(list)
        for row in all_rows:
            rows_by_loa[row["loa_number"]].append(row)

        # Build response: one object per work
        result = []
        for work in works:
            loa      = work.loa_number or ""
            raw_rows = rows_by_loa.get(loa, [])

            entries = []
            for row in raw_rows:
                entry = dict(row)
                entry["warnings"] = _validate_entry(row, work, items_by_work)
                entries.append(entry)

            # Sort entries newest first
            entries.sort(key=lambda e: e["datetime"], reverse=True)

            warning_count = sum(1 for e in entries if e["warnings"])

            result.append({
                "work_id":         work.id,
                "loa_number":      loa,
                "contractor_name": work.contractor_name or "",
                "name_of_work":    work.name_of_work or "",
                "tender_number":   work.tender_number or "",
                "consignee":       work.consignee or "",
                "date_of_completion": work.date_of_completion or "",
                "items":           items_detail[work.id],
                "entries":         entries,
                "entry_count":     len(entries),
                "warning_count":   warning_count,
            })

        return Response({
            "works":        result,
            "sheet_errors": sheet_errors,
        })
