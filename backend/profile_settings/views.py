from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from users.models import UserProfile
from users.views import _user_data


class MyProfileView(APIView):
    """
    GET   /api/settings/profile/   — current user's own profile
    PATCH /api/settings/profile/   — self-update email, designation, mobile_number
    """

    def get(self, request):
        if not request.user.is_authenticated:
            return Response({'error': 'Login required.'}, status=status.HTTP_401_UNAUTHORIZED)
        return Response(_user_data(request.user))

    def patch(self, request):
        if not request.user.is_authenticated:
            return Response({'error': 'Login required.'}, status=status.HTTP_401_UNAUTHORIZED)

        user = request.user
        profile, _ = UserProfile.objects.get_or_create(user=user)

        if 'email' in request.data:
            user.email = (request.data['email'] or '').strip()
            user.save(update_fields=['email'])

        profile_fields = []
        if 'designation' in request.data:
            profile.designation = (request.data['designation'] or '').strip()
            profile_fields.append('designation')
        if 'mobile_number' in request.data:
            profile.mobile_number = (request.data['mobile_number'] or '').strip()
            profile_fields.append('mobile_number')
        if profile_fields:
            profile.save(update_fields=profile_fields)

        return Response(_user_data(user))
