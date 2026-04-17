from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status


class UserListView(APIView):
    def get(self, request):
        return Response(
            {'error': 'User management not yet implemented.'},
            status=status.HTTP_501_NOT_IMPLEMENTED,
        )


class UserCreateView(APIView):
    def post(self, request):
        return Response(
            {'error': 'User creation not yet implemented.'},
            status=status.HTTP_501_NOT_IMPLEMENTED,
        )
