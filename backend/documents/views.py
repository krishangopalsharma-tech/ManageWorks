from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status


class DocumentGeneratorView(APIView):
    def post(self, request, *args, **kwargs):
        return Response(
            {'error': 'Document generation not yet implemented.'},
            status=status.HTTP_501_NOT_IMPLEMENTED,
        )
