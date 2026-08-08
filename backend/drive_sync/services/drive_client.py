"""
Thin wrapper around the Drive API v3 REST endpoints, using a bare API key —
no OAuth/service-account. Works for files/folders shared as "Anyone with the
link". No google-api-python-client dependency; plain `requests` (already used
elsewhere in this codebase, e.g. add_work's GSheet import).
"""
import requests

DRIVE_API = 'https://www.googleapis.com/drive/v3'


class DriveAPIError(Exception):
    pass


def list_folder_files(folder_id, api_key, mime_type='application/pdf'):
    """Return [{'id', 'name', 'modifiedTime'}, ...] for PDFs directly inside
    the given public folder (non-recursive, no subfolder traversal)."""
    params = {
        'q':      f"'{folder_id}' in parents and trashed = false and mimeType = '{mime_type}'",
        'fields': 'files(id,name,modifiedTime)',
        'key':    api_key,
        'pageSize': 1000,
    }
    resp = requests.get(f'{DRIVE_API}/files', params=params, timeout=30)
    if resp.status_code != 200:
        raise DriveAPIError(f'Drive list failed ({resp.status_code}): {resp.text[:300]}')
    return resp.json().get('files', [])


def download_file(file_id, api_key):
    """Return raw PDF bytes for a public file."""
    params = {'alt': 'media', 'key': api_key}
    resp = requests.get(f'{DRIVE_API}/files/{file_id}', params=params, timeout=60)
    if resp.status_code != 200:
        raise DriveAPIError(f'Drive download failed ({resp.status_code}): {resp.text[:300]}')
    return resp.content
