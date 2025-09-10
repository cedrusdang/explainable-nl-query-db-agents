from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import FileViewSet, SessionViewSet, ChatViewSet, APIKeyViewSet

# Register viewsets with the router
router = DefaultRouter()

# TODO: Add more viewsets as needed
router.register(r'file', FileViewSet)
router.register(r'session', SessionViewSet)
router.register(r'chat', ChatViewSet)
router.register(r'apikey', APIKeyViewSet)

# Define the URL patterns for the core app
urlpatterns = [
    path('', include(router.urls)),
]