from django.shortcuts import render
from httpcore import Response
from .serializers import FileSerializer, SessionSerializer, ChatSerializer, APIKeySerializer
from rest_framework import viewsets
from .models import File, Session, Chat, APIKey
from django.conf import settings

MEDIA_ROOT = settings.MEDIA_ROOT

# Create your views here.
class FileViewSet(viewsets.ModelViewSet):
    # Allow mutliple file uploads with zip/.sql
    queryset = File.objects.all()
    serializer_class = FileSerializer

    # Handle file uploads
    def create(self, request, *args, **kwargs):
        files = request.FILES.getlist('files')
        for file in files:
            # For zip
            if file.name.endswith('.zip'):
                # Unzip and save all files
                import zipfile
                with zipfile.ZipFile(file, 'r') as zip_ref:
                    zip_ref.extractall(MEDIA_ROOT)
        else:
            # For all other files
            File.objects.create(file=file)
        return Response(status=201)

class SessionViewSet(viewsets.ModelViewSet):
    queryset = Session.objects.all()
    serializer_class = SessionSerializer

class ChatViewSet(viewsets.ModelViewSet):
    queryset = Chat.objects.all()
    serializer_class = ChatSerializer

class APIKeyViewSet(viewsets.ModelViewSet):
    queryset = APIKey.objects.all()
    serializer_class = APIKeySerializer