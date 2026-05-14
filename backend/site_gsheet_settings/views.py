from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from .models import SiteGSheet
from .serializers import SiteGSheetSerializer


class SiteGSheetListCreateView(APIView):
    def get(self, request):
        sheets = SiteGSheet.objects.all()
        return Response(SiteGSheetSerializer(sheets, many=True).data)

    def post(self, request):
        serializer = SiteGSheetSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class SiteGSheetDetailView(APIView):
    def get(self, request, pk):
        sheet = get_object_or_404(SiteGSheet, pk=pk)
        return Response(SiteGSheetSerializer(sheet).data)

    def put(self, request, pk):
        sheet = get_object_or_404(SiteGSheet, pk=pk)
        serializer = SiteGSheetSerializer(sheet, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        sheet = get_object_or_404(SiteGSheet, pk=pk)
        sheet.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
