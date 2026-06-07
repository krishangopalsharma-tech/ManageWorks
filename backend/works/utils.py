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
