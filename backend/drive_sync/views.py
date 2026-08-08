from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from users.views import _is_super_admin
from .models import DriveSyncSettings, DriveFolderLink, SyncedFile
from .services.sync import sync_user_folders


def _check_authenticated(user):
    return user.is_authenticated


class StatusView(APIView):
    """GET /api/drive-sync/status/ — current user's connection + needs-review count.
    Drives the Sidebar 'Sync Data' button's enabled state and badge."""

    def get(self, request):
        if not _check_authenticated(request.user):
            return Response({'error': 'Login required.'}, status=status.HTTP_401_UNAUTHORIZED)

        link = DriveFolderLink.objects.filter(user=request.user).first()
        if not link:
            return Response({
                'connected': False,
                'workbills_folder_url': '',
                'crn_folder_url': '',
                'last_synced_at': None,
                'needs_review_count': 0,
            })

        needs_review_count = SyncedFile.objects.filter(folder_link=link, status='needs_review').count()
        return Response({
            'connected':            bool(link.workbills_folder_id or link.crn_folder_id),
            'workbills_folder_url': link.workbills_folder_url,
            'crn_folder_url':       link.crn_folder_url,
            'last_synced_at':       link.last_synced_at,
            'needs_review_count':   needs_review_count,
        })


class ConnectView(APIView):
    """POST /api/drive-sync/connect/ — save the current user's own two folder links."""

    def post(self, request):
        if not _check_authenticated(request.user):
            return Response({'error': 'Login required.'}, status=status.HTTP_401_UNAUTHORIZED)

        workbills_url = (request.data.get('workbills_folder_url') or '').strip()
        crn_url       = (request.data.get('crn_folder_url') or '').strip()

        link, _ = DriveFolderLink.objects.get_or_create(user=request.user)
        link.workbills_folder_url = workbills_url
        link.crn_folder_url       = crn_url
        link.save()

        return Response({
            'connected':            bool(link.workbills_folder_id or link.crn_folder_id),
            'workbills_folder_url': link.workbills_folder_url,
            'crn_folder_url':       link.crn_folder_url,
        })


class RunSyncView(APIView):
    """POST /api/drive-sync/run/ — sync the current user's own folders (Workbills + CRN together)."""

    def post(self, request):
        if not _check_authenticated(request.user):
            return Response({'error': 'Login required.'}, status=status.HTTP_401_UNAUTHORIZED)

        link = DriveFolderLink.objects.filter(user=request.user).first()
        if not link or not (link.workbills_folder_id or link.crn_folder_id):
            return Response({'error': 'Connect your Drive folders in My Account first.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            summary = sync_user_folders(link)
        except RuntimeError as exc:
            return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as exc:
            return Response({'error': f'Sync failed: {exc}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response(summary)


class AdminOverviewView(APIView):
    """GET /api/drive-sync/admin/overview/ — superadmin: every consignee's connection
    status + a combined recent sync log across everyone."""

    def get(self, request):
        if not _is_super_admin(request.user):
            return Response({'error': 'Forbidden.'}, status=status.HTTP_403_FORBIDDEN)

        links = []
        for link in DriveFolderLink.objects.select_related('user').all():
            links.append({
                'user_id':             link.user.id,
                'username':            link.user.username,
                'name':                link.user.first_name,
                'workbills_connected': bool(link.workbills_folder_id),
                'crn_connected':       bool(link.crn_folder_id),
                'last_synced_at':      link.last_synced_at,
                'needs_review_count':  SyncedFile.objects.filter(folder_link=link, status='needs_review').count(),
                'error_count':         SyncedFile.objects.filter(folder_link=link, status='error').count(),
            })

        log = list(
            SyncedFile.objects
            .select_related('folder_link__user', 'matched_work')
            .exclude(status='synced')
            .order_by('-synced_at')[:200]
            .values(
                'id', 'filename', 'kind', 'status', 'reason', 'synced_at',
                'folder_link__user__username',
                'matched_work__loa_number',
            )
        )

        return Response({'links': links, 'log': log})


class AdminConfigView(APIView):
    """GET/PATCH /api/drive-sync/admin/config/ — superadmin: the Drive API key."""

    def get(self, request):
        if not _is_super_admin(request.user):
            return Response({'error': 'Forbidden.'}, status=status.HTTP_403_FORBIDDEN)
        cfg = DriveSyncSettings.objects.first()
        return Response({
            'has_api_key': bool(cfg and cfg.api_key),
            'is_active':   bool(cfg and cfg.is_active),
        })

    def patch(self, request):
        if not _is_super_admin(request.user):
            return Response({'error': 'Forbidden.'}, status=status.HTTP_403_FORBIDDEN)

        cfg, _ = DriveSyncSettings.objects.get_or_create(pk=1)
        if 'api_key' in request.data:
            new_key = (request.data.get('api_key') or '').strip()
            if new_key:
                cfg.api_key = new_key
        if 'is_active' in request.data:
            cfg.is_active = bool(request.data.get('is_active'))
        cfg.save()

        return Response({'has_api_key': bool(cfg.api_key), 'is_active': cfg.is_active})
