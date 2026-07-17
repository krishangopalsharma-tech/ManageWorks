from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, generics
from rest_framework.exceptions import PermissionDenied

from django.db.models import Q

from works.models import Work, WorkExtension
from works.serializers import WorkEditSerializer, WorkSerializer
from works.utils import is_admin_user as _is_admin, is_assigned_consignee as _is_work_consignee
from work_details.views import _base_queryset


def _check_can_modify_work(user, work):
    """Admin (is_staff or role='admin') can modify any work's metadata.
    Assigned consignee can modify only their own LOA's metadata. Everyone else is forbidden."""
    if not user.is_authenticated:
        raise PermissionDenied("Authentication required.")
    if _is_admin(user):
        return
    if _is_work_consignee(user, work):
        return
    raise PermissionDenied("You are not authorised to update this work.")


# ── Work list — now scoped, since entry submission has moved to the new
# supply_details/execution_details apps and no longer needs this to stay open
# for every consignee. Admin sees everything; assigned consignee sees only
# their own LOA; unassigned consignee sees nothing (empty list / 404).

class UpdateWorkSearchView(generics.ListAPIView):
    serializer_class = WorkSerializer

    def get_queryset(self):
        queryset = _base_queryset()
        if not _is_admin(self.request.user):
            queryset = queryset.filter(hrms_id=self.request.user.username)
        query = self.request.query_params.get('q', None)
        if query:
            queryset = queryset.filter(
                Q(loa_number__icontains=query) |
                Q(contractor_name__icontains=query) |
                Q(tender_number__icontains=query)
            )
        return queryset

    def list(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return Response({'error': 'Login required.'}, status=status.HTTP_401_UNAUTHORIZED)
        return super().list(request, *args, **kwargs)


class UpdateWorkRetrieveView(generics.RetrieveAPIView):
    serializer_class = WorkSerializer

    def retrieve(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return Response({'error': 'Login required.'}, status=status.HTTP_401_UNAUTHORIZED)
        return super().retrieve(request, *args, **kwargs)

    def get_queryset(self):
        queryset = _base_queryset()
        if not _is_admin(self.request.user):
            queryset = queryset.filter(hrms_id=self.request.user.username)
        return queryset


# ── Work-level edit / delete ──────────────────────────────────────────────────

class WorkUpdateDeleteView(generics.RetrieveUpdateDestroyAPIView):
    """PATCH /api/update-work/works/<pk>/  DELETE /api/update-work/works/<pk>/"""
    queryset = Work.objects.all()
    serializer_class = WorkEditSerializer

    def partial_update(self, request, *args, **kwargs):
        instance = self.get_object()
        _check_can_modify_work(request.user, instance)

        serializer = WorkEditSerializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        if 'extensions' in request.data:
            instance.extensions.all().delete()
            for ext in request.data.get('extensions', []):
                date_val = (ext.get('extension_date') or '').strip()
                if date_val:
                    ld_type = (ext.get('ld_type') or 'without_ld').strip()
                    ld_amount = (ext.get('ld_amount') or '').strip()
                    WorkExtension.objects.create(
                        work=instance,
                        extension_date=date_val,
                        ld_type=ld_type,
                        ld_amount=ld_amount if ld_type == 'with_ld' else '',
                    )

        return Response(serializer.data)

    def destroy(self, _request, *args, **kwargs):
        return Response(
            {'error': 'Use DELETE /api/delete-log/works/<pk>/ with a reason to delete an LOA.'},
            status=status.HTTP_403_FORBIDDEN,
        )
