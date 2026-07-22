import re


def contractor_nickname(name: str) -> str:
    """First letter of each word: 'TIRUPATI CONSTRUCTION AND TRANSPORTERS' → 'TCAT'."""
    if not name:
        return ''
    words = re.split(r'[\s.,&()/\-]+', name)
    return ''.join(w[0].upper() for w in words if w and w[0].isalpha())


# ── Entry-level privacy helpers ────────────────────────────────────────────────

def is_admin_user(user):
    if user.is_staff:
        return True
    profile = getattr(user, 'profile', None)
    return profile is not None and profile.role == 'admin'


def is_assigned_consignee(user, work):
    """True when this user is the primary consignee on record for the given Work (matched via hrms_id == username)."""
    return bool(work.hrms_id and work.hrms_id == user.username)


def can_see_all_entries(user, work):
    return is_admin_user(user) or is_assigned_consignee(user, work)


# ── Financial-field redaction (Work Details "progress-view-only") ─────────────
#
# Note: per-item unit_rate_rs/unit_rate_below/total_amount are deliberately NOT
# redacted — the progress-percentage cards (supply/execution/overall) are cost-
# weighted using total_amount, and Item Progress already shows these fields to
# everyone unredacted (works/serializers.py WorkItemSerializer, fields='__all__').
# Redacting them here would silently zero out progress % for non-owners instead
# of just hiding money, which isn't what "progress-view-only" means.

_FINANCIAL_WORK_FIELDS = ('contract_agreement', 'contractor_address', 'bill_billing')
_FINANCIAL_EXTENSION_FIELDS = ('ld_amount',)


def redact_financials(data: dict) -> dict:
    """
    Strip contract-identity and billing figures from a serialized Work dict in
    place. Used for viewers who aren't Admin/Super Admin and aren't this LOA's
    assigned consignee.
    """
    for f in _FINANCIAL_WORK_FIELDS:
        data.pop(f, None)
    for ext in data.get('extensions') or []:
        for f in _FINANCIAL_EXTENSION_FIELDS:
            ext.pop(f, None)
    return data


def pad_loa(raw):
    """Normalise LOA to 14 digits — Excel/PDF often strips leading zeros."""
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
