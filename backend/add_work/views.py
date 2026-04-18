import os
import re
import tempfile
import urllib.request
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .services.excel_parser import parse_and_save_work_excel


def _sheet_id_from_url(url):
    """Extract the spreadsheet ID from a Google Sheets sharing URL."""
    match = re.search(r'/spreadsheets/d/([a-zA-Z0-9_-]+)', url)
    if not match:
        raise ValueError("Could not parse a Google Sheets ID from the provided link.")
    return match.group(1)


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
                items_created = parse_and_save_work_excel(tmp_path)
                os.remove(tmp_path)
                return Response({'success': items_created}, status=status.HTTP_201_CREATED)
            except Exception as e:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
                return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

        if link:
            tmp_path = None
            try:
                sheet_id = _sheet_id_from_url(link.strip())
                export_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=xlsx"
                with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
                    tmp_path = tmp.name
                urllib.request.urlretrieve(export_url, tmp_path)
                items_created = parse_and_save_work_excel(tmp_path)
                os.remove(tmp_path)
                return Response({'success': items_created}, status=status.HTTP_201_CREATED)
            except Exception as e:
                if tmp_path and os.path.exists(tmp_path):
                    os.remove(tmp_path)
                return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
