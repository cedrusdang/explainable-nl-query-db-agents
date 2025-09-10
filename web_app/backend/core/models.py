from django.db import models
from django.conf import settings

# Create your models here.
class File(models.Model):
    # SQL DB logging to store uploaded SQL files
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    # File send to /backend/media/sql_files/
    file = models.FileField(upload_to='sql_files/')
    time = models.DateTimeField(auto_now_add=True)

class Session(models.Model):
    # Store user sessions for chat history
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    start_time = models.DateTimeField(auto_now_add=True)

class Chat(models.Model):
    # Log of user queries and corresponding SQL queries
    session = models.ForeignKey(Session, on_delete=models.CASCADE, related_name='chats')
    time = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    agent = models.CharField(max_length=1) # Name as a, b, c, d
    # Type of the response: sql, text, json, etc.
    type = models.CharField(max_length=10)
    prompt = models.TextField()
    response = models.TextField()

class APIKey(models.Model):
    # Store API keys for different LLMs
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    api_key = models.TextField()
