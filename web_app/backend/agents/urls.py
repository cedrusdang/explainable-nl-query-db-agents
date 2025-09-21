from django.urls import path
from .views import api_key_view

urlpatterns = [
    path("api-key/", api_key_view, name="api-key"),
]