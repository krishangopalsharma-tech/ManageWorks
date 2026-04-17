import os
import tempfile
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .services.excel_parser import parse_and_save_work_excel


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
            return Response({'error': 'Sheet link import not fully implemented yet'}, status=status.HTTP_501_NOT_IMPLEMENTED)
