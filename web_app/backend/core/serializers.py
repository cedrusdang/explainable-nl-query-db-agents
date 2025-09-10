from rest_framework import serializers
from .models import File, Session, Chat, APIKey

class FileSerializer(serializers.ModelSerializer):
    class Meta:
        model = File
        fields = ['id', 'file', 'time']

class SessionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Session
        fields = ['id', 'user', 'start_time']

class ChatSerializer(serializers.ModelSerializer):
    class Meta:
        model = Chat
        fields = ['id', 'time', 'user', 'agent', 'prompt', 'response']


class APIKeySerializer(serializers.ModelSerializer):
    class Meta:
        model = APIKey
        fields = ['id', 'user', 'api_key']