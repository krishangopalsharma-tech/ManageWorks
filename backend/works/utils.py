import re


def contractor_nickname(name: str) -> str:
    """First letter of each word: 'TIRUPATI CONSTRUCTION AND TRANSPORTERS' → 'TCAT'."""
    if not name:
        return ''
    words = re.split(r'[\s.,&()/\-]+', name)
    return ''.join(w[0].upper() for w in words if w and w[0].isalpha())
