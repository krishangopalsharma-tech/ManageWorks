from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from .models import UserProfile
from works.models import Work
from email_service.mailer import send_password_email


def _user_data(user):
    from site_register.models import RlyTelegramLink
    profile = getattr(user, 'profile', None)
    tg_link = getattr(user, 'telegram_link', None)
    tg_linked = bool(tg_link and tg_link.is_verified)
    tg_chat_id = tg_link.telegram_chat_id if (tg_link and tg_linked) else None
    if not tg_linked:
        try:
            rly = RlyTelegramLink.objects.get(system_user=user, is_verified=True)
            tg_linked = True
            tg_chat_id = rly.telegram_chat_id
        except RlyTelegramLink.DoesNotExist:
            pass
    return {
        'id':              user.id,
        'hrms_id':         user.username,
        'name':            user.first_name,
        'email':           user.email,
        'designation':     profile.designation if profile else '',
        'mobile_number':   profile.mobile_number if profile else '',
        'role':            profile.role         if profile else ('admin' if user.is_staff else 'consignee'),
        'is_approved':     profile.is_approved  if profile else user.is_staff,
        'telegram_linked': tg_linked,
        'telegram_chat_id': tg_chat_id,
    }


@method_decorator(csrf_exempt, name='dispatch')
class RegisterView(APIView):
    def post(self, request):
        data        = request.data
        name        = data.get('name', '').strip()
        designation = data.get('designation', '').strip()
        hrms_id     = data.get('hrms_id', '').strip()
        password    = data.get('password', '')
        email       = data.get('email', '').strip()

        if not all([name, designation, hrms_id, password, email]):
            return Response({'error': 'All fields required.'}, status=status.HTTP_400_BAD_REQUEST)

        if User.objects.filter(username=hrms_id).exists():
            return Response({'error': 'User ID already registered.'}, status=status.HTTP_400_BAD_REQUEST)

        user = User.objects.create_user(
            username   = hrms_id,
            password   = password,
            first_name = name,
            email      = email,
            is_active  = True,
        )
        UserProfile.objects.create(
            user           = user,
            designation    = designation,
            is_approved    = False,
            role           = 'consignee',
            plain_password = password,
        )
        return Response({'message': 'Registration submitted. Await admin approval.'}, status=status.HTTP_201_CREATED)


@method_decorator(csrf_exempt, name='dispatch')
class ForgotPasswordView(APIView):
    def post(self, request):
        hrms_id = request.data.get('hrms_id', '').strip()
        if not hrms_id:
            return Response({'error': 'User ID required.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = User.objects.get(username=hrms_id)
        except User.DoesNotExist:
            # Generic message to avoid user enumeration
            return Response({'message': 'If that User ID exists, the password has been sent to the registered email.'})

        profile = getattr(user, 'profile', None)
        if not profile or not user.email:
            return Response({'message': 'If that User ID exists, the password has been sent to the registered email.'})

        try:
            send_password_email(
                to_email       = user.email,
                user_name      = user.first_name or user.username,
                hrms_id        = user.username,
                plain_password = profile.plain_password,
            )
        except Exception:
            return Response({'error': 'Could not send email. Contact admin.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response({'message': 'If that User ID exists, the password has been sent to the registered email.'})


@method_decorator(csrf_exempt, name='dispatch')
class LoginView(APIView):
    def post(self, request):
        hrms_id  = request.data.get('hrms_id', '').strip()
        password = request.data.get('password', '')

        user = authenticate(request, username=hrms_id, password=password)
        if user is None:
            return Response({'error': 'Invalid User ID or password.'}, status=status.HTTP_401_UNAUTHORIZED)

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
        if not _is_admin(request.user):
            return Response({'error': 'Forbidden.'}, status=status.HTTP_403_FORBIDDEN)

        profiles = UserProfile.objects.filter(is_approved=False).select_related('user')
        return Response([
            {
                'id':          p.user.id,
                'hrms_id':     p.user.username,
                'name':        p.user.first_name,
                'designation': p.designation,
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
        profiles = UserProfile.objects.filter(is_approved=True).select_related('user', 'user__telegram_link')
        return Response([
            {
                'id':              p.user.id,
                'hrms_id':         p.user.username,
                'name':            p.user.first_name,
                'designation':     p.designation,
                'role':            p.role,
                'email':           p.user.email,
                'telegram_linked': bool(
                    getattr(p.user, 'telegram_link', None) and
                    p.user.telegram_link.is_verified
                ),
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


def _is_super_admin(user):
    """Stricter than _is_admin — only the single 'admin' User ID, for
    sensitive settings (SMTP/Telegram bot credentials) other admins
    should not be able to view or change."""
    return user.is_authenticated and user.username == 'admin'


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
        if 'email' in request.data:
            profile.user.email = (request.data['email'] or '').strip()
            profile.user.save(update_fields=['email'])
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


class MyWorksView(APIView):
    """GET /api/auth/my-works/ — LOAs assigned to the logged-in consignee."""

    def get(self, request):
        if not request.user.is_authenticated:
            return Response({'error': 'Login required.'}, status=status.HTTP_401_UNAUTHORIZED)
        works = Work.objects.filter(hrms_id=request.user.username).values(
            'id', 'loa_number', 'tender_number',
            'contractor_name', 'name_of_work', 'date_of_completion',
        ).order_by('loa_number')
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
        if hrms_id:
            try:
                new_user = User.objects.get(username=hrms_id)
                profile = getattr(new_user, 'profile', None)
                work.consignee = (profile.designation if profile and profile.designation else None) or new_user.first_name or new_user.username
            except User.DoesNotExist:
                pass
        else:
            work.consignee = ''
        work.save(update_fields=['hrms_id', 'consignee'])
        return Response({
            'id':               work.id,
            'hrms_id':          work.hrms_id,
            'loa_number':       work.loa_number,
            'contractor_name':  work.contractor_name,
            'consignee':        work.consignee,
        })
