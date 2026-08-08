"""
Core sync engine — pulls PDFs from a consignee's own Drive folders, parses
them with the SAME parsers the manual-upload pages already use, and either
auto-commits (clean match, no warnings, correct owner) or logs needs_review
(anything ambiguous). Never force-writes a flagged file.

Called from both the manual "Sync Data" button (one user) and the 7am cron
(loops every connected user) — see views.py / management/commands/sync_drive_folders.py.
"""
import io
from django.db import transaction
from django.utils import timezone

from works.models import Work, WorkItem, WorkItemEntry
from works.utils import pad_loa
from financial_progress.models import BillRecord, BillItem
from financial_progress.pdf_parser import parse_bill_pdf
from financial_progress.views import _build_loa_lookup, _loa_cross_check
from supply_details.pdf_parser import parse_receipt_pdf
from supply_details.views import _sync_supplied_quantity

from ..models import DriveFolderLink, SyncedFile, DriveSyncSettings
from . import drive_client


def _normalize_serial(sno):
    try:
        return str(int(sno))
    except (ValueError, TypeError):
        return (sno or '').strip()


def _find_work_by_loa(loa_raw):
    loa_raw = (loa_raw or '').strip()
    if not loa_raw:
        return None
    candidates = {loa_raw, pad_loa(loa_raw), loa_raw.lstrip('0')}
    return Work.objects.filter(loa_number__in=candidates).first()


def _match_supply_item(work, serial_raw):
    """Receipts only carry a serial number (no schedule) — narrow to 'supply'
    category items first since a DMTR/receipt note is inherently a supply-side
    document; fall back to any-schedule match only if that's unambiguous too."""
    sno = _normalize_serial(serial_raw)
    if not sno:
        return None, 'No item Sl. No. found in PDF.'
    candidates = [wi for wi in WorkItem.objects.filter(work=work) if _normalize_serial(wi.serial_number) == sno]
    supply_candidates = [wi for wi in candidates if (wi.category or '') == 'supply']
    if len(supply_candidates) == 1:
        return supply_candidates[0], None
    if len(candidates) == 1:
        return candidates[0], None
    if not candidates:
        return None, f'Item Sl. No. "{sno}" not found in this LOA.'
    return None, f'Item Sl. No. "{sno}" matches multiple items/schedules — ambiguous, verify manually.'


def _log(folder_link, drive_file_id, filename, modified_time, kind, status_, reason, work):
    obj, _ = SyncedFile.objects.update_or_create(
        folder_link=folder_link, drive_file_id=drive_file_id,
        defaults=dict(
            filename=filename, modified_time=modified_time, kind=kind,
            status=status_, reason=reason, matched_work=work,
        ),
    )
    return obj


def _process_bill_file(folder_link, file_bytes, filename, drive_file_id, modified_time):
    user = folder_link.user
    try:
        parsed = parse_bill_pdf(io.BytesIO(file_bytes))
    except Exception as exc:
        return _log(folder_link, drive_file_id, filename, modified_time, 'bill', 'error', f'Parse failed: {exc}', None)

    work = _find_work_by_loa(parsed.get('loa_number'))
    if work is None:
        return _log(folder_link, drive_file_id, filename, modified_time, 'bill', 'needs_review',
                     f'LOA "{parsed.get("loa_number") or "?"}" not found in system.', None)

    if (work.hrms_id or '') != user.username:
        return _log(folder_link, drive_file_id, filename, modified_time, 'bill', 'needs_review',
                     f'LOA "{work.loa_number}" is not assigned to this consignee.', work)

    loa_lookup = _build_loa_lookup(work)
    _loa_cross_check(parsed, loa_lookup)

    warnings = parsed.get('warnings') or []
    if warnings:
        return _log(folder_link, drive_file_id, filename, modified_time, 'bill', 'needs_review',
                     ' | '.join(warnings), work)

    bill_number = (parsed.get('bill_number') or '').strip()
    if not bill_number:
        return _log(folder_link, drive_file_id, filename, modified_time, 'bill', 'needs_review',
                     'No bill number found in PDF.', work)

    if BillRecord.objects.filter(work=work, bill_number=bill_number).exists():
        return _log(folder_link, drive_file_id, filename, modified_time, 'bill', 'needs_review',
                     f'Bill "{bill_number}" already exists for this LOA.', work)

    with transaction.atomic():
        bill = BillRecord.objects.create(
            work=work,
            bill_number=bill_number,
            bill_date=parsed.get('bill_date') or None,
            loa_number=parsed.get('loa_number', ''),
            agreement_number=parsed.get('agreement_number', ''),
            uploaded_by=user,
        )
        created_items = 0
        for item in parsed.get('items', []):
            rate = float(item.get('agreement_rate') or 0)
            qty  = float(item.get('current_agmt_qty') or 0)
            amt  = float(item.get('amt_total') or 0)
            if rate == 0 and qty == 0 and amt == 0:
                continue
            raw_original_qty = item.get('original_agmt_qty')
            BillItem.objects.create(
                bill_record       = bill,
                schedule_name     = item.get('schedule_name', ''),
                item_number       = item.get('item_number', ''),
                description       = item.get('description', ''),
                unit              = item.get('unit', ''),
                agreement_rate    = rate,
                original_agmt_qty = float(raw_original_qty) if raw_original_qty not in (None, '') else None,
                current_agmt_qty  = qty,
                qty_upto_date     = float(item.get('qty_upto_date') or 0),
                amt_total         = amt,
            )
            created_items += 1

    return _log(folder_link, drive_file_id, filename, modified_time, 'bill', 'synced',
                f'Bill "{bill_number}" saved with {created_items} items.', work)


def _process_receipt_file(folder_link, file_bytes, filename, drive_file_id, modified_time):
    user = folder_link.user
    try:
        parsed = parse_receipt_pdf(io.BytesIO(file_bytes))
    except Exception as exc:
        return _log(folder_link, drive_file_id, filename, modified_time, 'receipt', 'error', f'Parse failed: {exc}', None)

    warnings = list(parsed.get('parse_warnings') or [])

    work = _find_work_by_loa(parsed.get('loa_number'))
    if work is None:
        return _log(folder_link, drive_file_id, filename, modified_time, 'receipt', 'needs_review',
                     f'LOA "{parsed.get("loa_number") or "?"}" not found in system.', None)

    if (work.hrms_id or '') != user.username:
        return _log(folder_link, drive_file_id, filename, modified_time, 'receipt', 'needs_review',
                     f'LOA "{work.loa_number}" is not assigned to this consignee.', work)

    work_item, match_err = _match_supply_item(work, parsed.get('serial_number'))
    if match_err:
        warnings.append(match_err)

    qty = parsed.get('quantity')
    receive_note_no = (parsed.get('receive_note_no') or '').strip()
    if not qty or qty <= 0:
        warnings.append('Qty. Accepted not found or not positive.')
    if not receive_note_no:
        warnings.append('DMTR No. (receive note) not found.')

    if warnings or work_item is None:
        return _log(folder_link, drive_file_id, filename, modified_time, 'receipt', 'needs_review',
                     ' | '.join(warnings) or 'Could not match item.', work)

    if (work_item.category or '').strip() == WorkItem.CATEGORY_EXECUTION:
        return _log(folder_link, drive_file_id, filename, modified_time, 'receipt', 'needs_review',
                     'Matched item is an Execution item — supply entries not applicable.', work)

    if WorkItemEntry.objects.filter(entry_type='supply', receive_note_no=receive_note_no).exists():
        return _log(folder_link, drive_file_id, filename, modified_time, 'receipt', 'needs_review',
                     f'Receive Note No. "{receive_note_no}" already exists.', work)

    WorkItemEntry.objects.create(
        work_item=work_item,
        entry_type='supply',
        quantity=qty,
        receive_note_no=receive_note_no,
        date_of_receipt=parsed.get('date_of_receipt') or None,
        challan_no=parsed.get('challan_no') or '',
        submitted_by=user,
        submitted_by_designation=getattr(getattr(user, 'profile', None), 'designation', None),
    )
    _sync_supplied_quantity(work_item)

    return _log(folder_link, drive_file_id, filename, modified_time, 'receipt', 'synced',
                f'Receipt "{receive_note_no}" saved ({qty} {parsed.get("unit", "")}).', work)


def sync_user_folders(folder_link):
    """Sync one consignee's Workbills + CRN folders. Returns a summary dict."""
    settings_row = DriveSyncSettings.objects.filter(is_active=True).first()
    if not settings_row or not settings_row.api_key:
        raise RuntimeError('Drive Sync is not configured — ask a Super Admin to add the API key under Settings > Drive Sync.')
    api_key = settings_row.api_key

    summary = {'bills_synced': 0, 'receipts_synced': 0, 'needs_review': 0, 'errors': 0}

    jobs = []
    if folder_link.workbills_folder_id:
        jobs.append(('bill', folder_link.workbills_folder_id, _process_bill_file))
    if folder_link.crn_folder_id:
        jobs.append(('receipt', folder_link.crn_folder_id, _process_receipt_file))

    for kind, folder_id, handler in jobs:
        try:
            files = drive_client.list_folder_files(folder_id, api_key)
        except drive_client.DriveAPIError:
            summary['errors'] += 1
            continue

        # Only truly 'synced' files are skipped on an unchanged modifiedTime —
        # needs_review/error files are retried every run (cheap: bounded by
        # however many are actually stuck) so a fix on our side (e.g. adding
        # the missing Work) gets picked up without any manual "retry" action.
        already_synced = {
            sf.drive_file_id: sf.modified_time
            for sf in SyncedFile.objects.filter(folder_link=folder_link, kind=kind, status='synced')
        }

        for f in files:
            fid, name, mtime = f['id'], f.get('name', ''), f.get('modifiedTime', '')
            if already_synced.get(fid) == mtime:
                continue

            try:
                content = drive_client.download_file(fid, api_key)
            except drive_client.DriveAPIError as exc:
                _log(folder_link, fid, name, mtime, kind, 'error', str(exc), None)
                summary['errors'] += 1
                continue

            result = handler(folder_link, content, name, fid, mtime)
            if result.status == 'synced':
                summary['bills_synced' if kind == 'bill' else 'receipts_synced'] += 1
            elif result.status == 'needs_review':
                summary['needs_review'] += 1
            else:
                summary['errors'] += 1

    folder_link.last_synced_at = timezone.now()
    folder_link.save(update_fields=['last_synced_at'])
    return summary


def sync_all_folders():
    """Cron entry point — loop every connected consignee."""
    totals = {'bills_synced': 0, 'receipts_synced': 0, 'needs_review': 0, 'errors': 0, 'users_synced': 0}
    for folder_link in DriveFolderLink.objects.select_related('user').all():
        if not folder_link.workbills_folder_id and not folder_link.crn_folder_id:
            continue
        try:
            summary = sync_user_folders(folder_link)
        except RuntimeError:
            break  # not configured — no point looping further
        for k in ('bills_synced', 'receipts_synced', 'needs_review', 'errors'):
            totals[k] += summary[k]
        totals['users_synced'] += 1
    return totals
