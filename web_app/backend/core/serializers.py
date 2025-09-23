from rest_framework import serializers
from .models import Files, APIKeys

class FilesSerializer(serializers.ModelSerializer):
    class Meta:
        model = Files
        fields = ['id', 'user', 'file', 'database', 'time']

# Chats model removed; frontend stores chat session in localStorage and can POST to download endpoint

class APIKeysSerializer(serializers.ModelSerializer):
    class Meta:
        model = APIKeys
        fields = ['id', 'user', 'api_key']