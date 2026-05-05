from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from .models import UserProfile
from works.models import Work


def _user_data(user):
    profile = getattr(user, 'profile', None)
    return {
        'id':          user.id,
        'hrms_id':     user.username,
        'name':        user.first_name,
        'designation': profile.designation if profile else '',
        'pf_number':   profile.pf_number   if profile else '',
        'role':        profile.role         if profile else ('admin' if user.is_staff else 'consignee'),
        'is_approved': profile.is_approved  if profile else user.is_staff,
    }


@method_decorator(csrf_exempt, name='dispatch')
class RegisterView(APIView):
    def post(self, request):
        data        = request.data
        name        = data.get('name', '').strip()
        designation = data.get('designation', '').strip()
        hrms_id     = data.get('hrms_id', '').strip()
        pf_number   = data.get('pf_number', '').strip()
        password    = data.get('password', '')

        if not all([name, designation, hrms_id, pf_number, password]):
            return Response({'error': 'All fields required.'}, status=status.HTTP_400_BAD_REQUEST)

        if User.objects.filter(username=hrms_id).exists():
            return Response({'error': 'HRMS ID already registered.'}, status=status.HTTP_400_BAD_REQUEST)

        user = User.objects.create_user(
            username   = hrms_id,
            password   = password,
            first_name = name,
            is_active  = True,
        )
        UserProfile.objects.create(
            user        = user,
            designation = designation,
            pf_number   = pf_number,
            is_approved = False,
            role        = 'consignee',
        )
        return Response({'message': 'Registration submitted. Await admin approval.'}, status=status.HTTP_201_CREATED)


@method_decorator(csrf_exempt, name='dispatch')
class LoginView(APIView):
    def post(self, request):
        hrms_id  = request.data.get('hrms_id', '').strip()
        password = request.data.get('password', '')

        user = authenticate(request, username=hrms_id, password=password)
        if user is None:
            return Response({'error': 'Invalid HRMS ID or password.'}, status=status.HTTP_401_UNAUTHORIZED)

        # Staff/superusers bypass approval check
        if not user.is_staff:
            profile = getattr(user, 'profile', None)
            if profile is None or not profile.is_approved:
                return Response({'error': 'Account pending admin approval.'}, status=status.HTTP_403_FORBIDDEN)

        login(request, user)
        return Response(_user_data(user))


class LogoutView(APIView):
    def post(self, request):
        logout(request)
        return Response({'message': 'Logged out.'})


class MeView(APIView):
    def get(self, request):
        if not request.user.is_authenticated:
            return Response({'authenticated': False}, status=status.HTTP_401_UNAUTHORIZED)
        return Response({'authenticated': True, **_user_data(request.user)})


class PendingUsersView(APIView):
    def get(self, request):
        if not request.user.is_authenticated or not request.user.is_staff:
            # Also allow users with admin role
            profile = getattr(request.user, 'profile', None)
            if not request.user.is_authenticated or (profile and profile.role != 'admin'):
                return Response({'error': 'Forbidden.'}, status=status.HTTP_403_FORBIDDEN)

        profiles = UserProfile.objects.filter(is_approved=False).select_related('user')
        return Response([
            {
                'id':          p.user.id,
                'hrms_id':     p.user.username,
                'name':        p.user.first_name,
                'designation': p.designation,
                'pf_number':   p.pf_number,
                'created_at':  p.created_at.strftime('%Y-%m-%d %H:%M'),
            }
            for p in profiles
        ])


class ApproveUserView(APIView):
    def post(self, request, user_id):
        if not _is_admin(request.user):
            return Response({'error': 'Forbidden.'}, status=status.HTTP_403_FORBIDDEN)
        try:
            profile = UserProfile.objects.get(user_id=user_id)
        except UserProfile.DoesNotExist:
            return Response({'error': 'User not found.'}, status=status.HTTP_404_NOT_FOUND)
        profile.is_approved = True
        profile.save()
        return Response({'message': 'User approved.'})


class RejectUserView(APIView):
    def delete(self, request, user_id):
        if not _is_admin(request.user):
            return Response({'error': 'Forbidden.'}, status=status.HTTP_403_FORBIDDEN)
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response({'error': 'User not found.'}, status=status.HTTP_404_NOT_FOUND)
        user.delete()
        return Response({'message': 'User rejected and removed.'})


class AllUsersView(APIView):
    def get(self, request):
        if not _is_admin(request.user):
            return Response({'error': 'Forbidden.'}, status=status.HTTP_403_FORBIDDEN)
        profiles = UserProfile.objects.filter(is_approved=True).select_related('user')
        return Response([
            {
                'id':          p.user.id,
                'hrms_id':     p.user.username,
                'name':        p.user.first_name,
                'designation': p.designation,
                'pf_number':   p.pf_number,
                'role':        p.role,
            }
            for p in profiles
        ])


class UpdateRoleView(APIView):
    def patch(self, request, user_id):
        if not _is_admin(request.user):
            return Response({'error': 'Forbidden.'}, status=status.HTTP_403_FORBIDDEN)
        role = request.data.get('role', '').strip()
        if role not in ('consignee', 'admin'):
            return Response({'error': 'Invalid role.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            profile = UserProfile.objects.get(user_id=user_id)
        except UserProfile.DoesNotExist:
            return Response({'error': 'User not found.'}, status=status.HTTP_404_NOT_FOUND)
        profile.role = role
        profile.save()
        return Response({'message': 'Role updated.'})


class RevokeUserView(APIView):
    def post(self, request, user_id):
        if not _is_admin(request.user):
            return Response({'error': 'Forbidden.'}, status=status.HTTP_403_FORBIDDEN)
        try:
            profile = UserProfile.objects.get(user_id=user_id)
        except UserProfile.DoesNotExist:
            return Response({'error': 'User not found.'}, status=status.HTTP_404_NOT_FOUND)
        profile.is_approved = False
        profile.save()
        return Response({'message': 'Access revoked.'})


def _is_admin(user):
    if not user.is_authenticated:
        return False
    if user.is_staff:
        return True
    profile = getattr(user, 'profile', None)
    return profile is not None and profile.role == 'admin'


class UpdateUserView(APIView):
    def patch(self, request, user_id):
        if not _is_admin(request.user):
            return Response({'error': 'Forbidden.'}, status=status.HTTP_403_FORBIDDEN)
        try:
            profile = UserProfile.objects.get(user_id=user_id)
        except UserProfile.DoesNotExist:
            return Response({'error': 'User not found.'}, status=status.HTTP_404_NOT_FOUND)
        if 'designation' in request.data:
            profile.designation = (request.data['designation'] or '').strip()
        if 'role' in request.data:
            role = (request.data['role'] or '').strip()
            if role not in ('consignee', 'admin'):
                return Response({'error': 'Invalid role.'}, status=status.HTTP_400_BAD_REQUEST)
            profile.role = role
        profile.save()
        return Response({'message': 'Updated.'})


class WorksListView(APIView):
    """GET /api/auth/works/ — lightweight works list for admin assignment UI."""

    def get(self, request):
        if not _is_admin(request.user):
            return Response({'error': 'Forbidden.'}, status=status.HTTP_403_FORBIDDEN)
        works = Work.objects.values(
            'id', 'loa_number', 'tender_number',
            'contractor_name', 'consignee', 'hrms_id', 'name_of_work',
        ).order_by('id')
        return Response(list(works))


class AssignWorkView(APIView):
    """
    POST /api/auth/assign-work/
    body: { work_id, hrms_id }   ← hrms_id='' to unassign
    Admin-only. Sets Work.hrms_id directly.
    """

    def post(self, request):
        if not _is_admin(request.user):
            return Response({'error': 'Forbidden.'}, status=status.HTTP_403_FORBIDDEN)
        work_id = request.data.get('work_id')
        hrms_id = (request.data.get('hrms_id') or '').strip()
        try:
            work = Work.objects.get(pk=work_id)
        except Work.DoesNotExist:
            return Response({'error': 'Work not found.'}, status=status.HTTP_404_NOT_FOUND)
        work.hrms_id = hrms_id
        work.save(update_fields=['hrms_id'])
        return Response({
            'id':               work.id,
            'hrms_id':          work.hrms_id,
            'loa_number':       work.loa_number,
            'contractor_name':  work.contractor_name,
            'consignee':        work.consignee,
        })
