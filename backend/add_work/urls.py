from django.urls import path
from .views import UploadWorkView

urlpatterns = [
    path('upload/', UploadWorkView.as_view(), name='upload_work'),
]
