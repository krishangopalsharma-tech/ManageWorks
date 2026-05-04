import os
import re
import shutil
import subprocess
import tempfile

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .services.excel_parser import parse_and_save_work_excel


def _sheet_id_from_url(url):
    match = re.search(r'/spreadsheets/d/([a-zA-Z0-9_-]+)', url)
    if not match:
        raise ValueError("Could not parse a Google Sheets ID from the provided link.")
    return match.group(1)


def _download_google_sheet(sheet_id, tmp_path):
    """Download a publicly shared Google Sheet as xlsx using curl."""
    if not shutil.which('curl'):
        raise ValueError("curl is not installed on the server.")

    export_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=xlsx"

    result = subprocess.run(
        ['curl', '-L', '--max-time', '30', '--silent', '--fail',
         '-o', tmp_path, '-w', '%{http_code}', export_url],
        capture_output=True, text=True, timeout=35,
    )

    http_code = result.stdout.strip()

    if result.returncode != 0:
        # curl exit code 22 = HTTP error (--fail triggered), 28 = timeout
        if result.returncode == 28:
            raise ValueError("Download timed out. Check your connection or try again.")
        if http_code in ('401', '403'):
            raise ValueError(
                f'Access denied (HTTP {http_code}). '
                'Make sure the sheet is shared as "Anyone with the link → Viewer".'
            )
        raise ValueError(
            f'Failed to download sheet (curl exit {result.returncode}, HTTP {http_code or "?"}). '
            'Make sure the Google Sheet is shared as "Anyone with the link".'
        )

    size = os.path.getsize(tmp_path) if os.path.exists(tmp_path) else 0
    if size < 1000:
        raise ValueError(
            'Downloaded file is too small — Google may have returned an error page. '
            'Make sure the sheet is shared as "Anyone with the link → Viewer".'
        )


def _parse_response(result):
    """Convert parser result dict → (response_data, http_status)."""
    s = result['status']
    if s == 'created':
        return (
            {'status': 'created', 'message': f"{result['items']} items uploaded successfully."},
            status.HTTP_201_CREATED,
        )
    if s == 'updated':
        return (
            {'status': 'updated', 'message': f"Work updated — {result['changes']} change(s) applied across {result['items']} items."},
            status.HTTP_200_OK,
        )
    # no_changes
    return (
        {'status': 'no_changes', 'message': f"Work already up to date — no changes found ({result['items']} items)."},
        status.HTTP_200_OK,
    )


class UploadWorkView(APIView):
    def post(self, request, *args, **kwargs):
        file_obj = request.FILES.get('file')
        link = request.data.get('link')

        if not file_obj and not link:
            return Response({'error': 'No file or link provided'}, status=status.HTTP_400_BAD_REQUEST)

        if file_obj:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
                for chunk in file_obj.chunks():
                    tmp.write(chunk)
                tmp_path = tmp.name
            try:
                result = parse_and_save_work_excel(tmp_path)
                os.remove(tmp_path)
                data, http_status = _parse_response(result)
                return Response(data, status=http_status)
            except Exception as e:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
                return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

        if link:
            tmp_path = None
            try:
                sheet_id = _sheet_id_from_url(link.strip())
                with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
                    tmp_path = tmp.name
                _download_google_sheet(sheet_id, tmp_path)
                result = parse_and_save_work_excel(tmp_path)
                os.remove(tmp_path)
                data, http_status = _parse_response(result)
                return Response(data, status=http_status)
            except Exception as e:
                if tmp_path and os.path.exists(tmp_path):
                    os.remove(tmp_path)
                return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
