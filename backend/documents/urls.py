from django.urls import path
from .views import DocumentGeneratorView

urlpatterns = [
    path('generate/', DocumentGeneratorView.as_view(), name='generate_document'),
]
