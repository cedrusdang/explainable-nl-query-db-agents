# backend/agents/views.py
import json
from django.http import StreamingHttpResponse
from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.conf import settings

from utils.get_keys import get_api_key
from utils import sql_connector                     # <-- import from utils
from . import a_db_select, b_table_select, c_sql_generate

MEDIA_ROOT = settings.MEDIA_ROOT

AGENTS = {
    "a-db-select": a_db_select.run,
    "b-table-select": b_table_select.run,
    "c-sql-generate": c_sql_generate.run,
    "d-sql-connector": sql_connector.run,          # <-- final agent from utils
}


# Base OAuth ViewSet #
class OAuthRestrictedModelViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {"error": serializer.errors}, status=status.HTTP_400_BAD_REQUEST
            )
        try:
            self.perform_create(serializer)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response(
                {"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class AgentViewSet(OAuthRestrictedModelViewSet):
    def create(self, request, pk=None):
        api_key = get_api_key()

        # Server-Sent Events response generator
        def event_stream():
            result = request.data  # initial input
            for name, func in AGENTS.items():
                try:
                    # pass api_key for A/B/C; sql_connector ignores it safely
                    result = func(api_key, result, media_path=MEDIA_ROOT)
                    yield f"data: {json.dumps({name: result})}\n\n"
                except Exception as e:
                    yield f"data: {json.dumps({name: 'error', 'detail': str(e)})}\n\n"

        return StreamingHttpResponse(event_stream(), content_type="text/event-stream")
