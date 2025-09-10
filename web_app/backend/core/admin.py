from django.contrib import admin
from .models import SQLFile, ChatHistory

# Register your models here.
admin.site.register(SQLFile) # For SQL file upload logging
admin.site.register(ChatHistory) # For user-agent chat history logging