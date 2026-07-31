from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.models import User
from django.contrib.auth.validators import UnicodeUsernameValidator
from django.core.exceptions import ValidationError
from django.db import transaction
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from users.models import UserProfile
from users.views import _user_data
from works.models import Work

_username_validator = UnicodeUsernameValidator()


class MyProfileView(APIView):
    """
    GET   /api/settings/profile/   — current user's own profile
    PATCH /api/settings/profile/   — self-update User ID, email, designation, mobile_number
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

        if 'hrms_id' in request.data:
            new_id = (request.data['hrms_id'] or '').strip()
            if not new_id:
                return Response({'error': 'User ID cannot be empty.'}, status=status.HTTP_400_BAD_REQUEST)
            try:
                _username_validator(new_id)
            except ValidationError as exc:
                return Response({'error': exc.messages[0]}, status=status.HTTP_400_BAD_REQUEST)
            if new_id != user.username:
                if User.objects.filter(username__iexact=new_id).exists():
                    return Response({'error': 'User ID already taken.'}, status=status.HTTP_400_BAD_REQUEST)
                old_id = user.username
                with transaction.atomic():
                    # Work.hrms_id is a plain string mirror of username (no FK) —
                    # every assigned-work lookup across the app keys off it, so it
                    # must be renamed in lockstep or the user's LOAs "disappear".
                    # Bulk .update() deliberately skips Work's pre/post_save signals
                    # (Telegram reassignment notices, role auto-convert) — this is
                    # a rename, not a reassignment, so those must NOT fire.
                    Work.objects.filter(hrms_id=old_id).update(hrms_id=new_id)
                    user.username = new_id
                    user.save(update_fields=['username'])

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


class ChangePasswordView(APIView):
    """POST /api/settings/profile/password/ — self-service password change."""

    def post(self, request):
        if not request.user.is_authenticated:
            return Response({'error': 'Login required.'}, status=status.HTTP_401_UNAUTHORIZED)

        user            = request.user
        current_password = request.data.get('current_password', '')
        new_password      = request.data.get('new_password', '')

        if not user.check_password(current_password):
            return Response({'error': 'Current password is incorrect.'}, status=status.HTTP_400_BAD_REQUEST)
        if not new_password or len(new_password) < 6:
            return Response({'error': 'New password must be at least 6 characters.'}, status=status.HTTP_400_BAD_REQUEST)

        user.set_password(new_password)
        user.save(update_fields=['password'])

        profile = getattr(user, 'profile', None)
        if profile:
            profile.plain_password = new_password
            profile.save(update_fields=['plain_password'])

        # set_password rotates the session auth hash — without this the user
        # who just changed their own password gets logged out immediately.
        update_session_auth_hash(request, user)

        return Response({'message': 'Password updated.'})
