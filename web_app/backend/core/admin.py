from django.contrib import admin
from .models import File, Session, Chat, APIKey

# Register your models here.
admin.site.register(File) # For files upload logging
admin.site.register(Session) # For session logging
admin.site.register(Chat) # For chat logging
admin.site.register(APIKey) # For API key management
