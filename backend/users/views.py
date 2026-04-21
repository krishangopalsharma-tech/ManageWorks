from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status


class MeView(APIView):
    """GET /api/users/me/ — return the currently authenticated user."""
    def get(self, request):
        if not request.user.is_authenticated:
            return Response({'id': None, 'username': None, 'role': None})
        return Response({
            'id':       request.user.id,
            'username': request.user.username,
            'role':     getattr(getattr(request.user, 'profile', None), 'role', 'observer'),
        })


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
