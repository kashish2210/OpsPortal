from django.db import connection
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response


@extend_schema(
    summary="Health check",
    description="Liveness/readiness probe. Verifies the database connection.",
    responses={200: dict, 503: dict},
    auth=[],
)
@api_view(["GET"])
@permission_classes([AllowAny])
def health_check(request):
    """Used by Docker's healthcheck and by uptime monitors."""
    database_ok = True
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except Exception:  # pragma: no cover - only hit when the DB is down
        database_ok = False

    payload = {
        "status": "ok" if database_ok else "degraded",
        "database": "ok" if database_ok else "unavailable",
        "time": timezone.now().isoformat(),
    }
    return Response(payload, status=200 if database_ok else 503)
