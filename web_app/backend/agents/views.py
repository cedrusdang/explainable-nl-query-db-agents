from django.conf import settings
from pathlib import Path
from core.views import OAuthRestrictedModelViewSet

## Helpers ##
from django.http import JsonResponse
from utils.get_keys import get_api_key

def api_key_view(request):
    key = get_api_key()
    return JsonResponse({"api_key": key})
