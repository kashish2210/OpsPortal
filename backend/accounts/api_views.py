"""Authentication and user-management REST endpoints."""

from django.contrib.auth import get_user_model
from django.db.models import Q
from drf_spectacular.utils import OpenApiExample, OpenApiResponse, extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView

from core.permissions import IsAdminRole

from .models import Role
from .serializers import (
    ChangePasswordSerializer,
    LoginSerializer,
    LogoutSerializer,
    ProfileUpdateSerializer,
    RoleSerializer,
    TokenPairSerializer,
    UserSerializer,
    UserWriteSerializer,
    build_token_response,
)

User = get_user_model()


@extend_schema(
    tags=["Auth"],
    summary="Log in",
    description="Exchange a username (or e-mail) and password for a JWT pair.",
    request=LoginSerializer,
    responses={200: TokenPairSerializer, 400: OpenApiResponse(description="Invalid credentials")},
    examples=[
        OpenApiExample(
            "Admin login",
            value={"username": "admin", "password": "Admin@12345"},
            request_only=True,
        )
    ],
    auth=[],
)
class LoginAPIView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_scope = "login"
    serializer_class = LoginSerializer

    def post(self, request):
        serializer = LoginSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        return Response(build_token_response(user, {"request": request}), status=status.HTTP_200_OK)


@extend_schema(
    tags=["Auth"],
    summary="Refresh access token",
    description="Exchange a valid refresh token for a new access token.",
    auth=[],
)
class RefreshAPIView(TokenRefreshView):
    permission_classes = [AllowAny]
    authentication_classes = []


@extend_schema(
    tags=["Auth"],
    summary="Log out",
    description="Blacklists the supplied refresh token so it can no longer be used.",
    request=LogoutSerializer,
    responses={205: OpenApiResponse(description="Token blacklisted")},
)
class LogoutAPIView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = LogoutSerializer

    def post(self, request):
        serializer = LogoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            RefreshToken(serializer.validated_data["refresh"]).blacklist()
        except TokenError:
            # An already-expired/blacklisted token is not an error for the
            # client: the desired end state (logged out) is reached either way.
            pass
        return Response(status=status.HTTP_205_RESET_CONTENT)


@extend_schema(
    tags=["Auth"],
    summary="Exchange a Django session for a JWT pair",
    description=(
        "Called by the React app after a user signs in through the "
        "server-rendered Django login page. Requires an active session cookie."
    ),
    request=None,
    responses={200: TokenPairSerializer, 403: OpenApiResponse(description="No active session")},
)
class SessionTokenAPIView(APIView):
    """Bridges the Django-rendered auth pages and the SPA."""

    permission_classes = [IsAuthenticated]
    serializer_class = TokenPairSerializer

    def post(self, request):
        return Response(build_token_response(request.user, {"request": request}))

    def get(self, request):
        return self.post(request)


@extend_schema(tags=["Auth"], summary="Current user")
class MeAPIView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = UserSerializer

    def get(self, request):
        return Response(UserSerializer(request.user, context={"request": request}).data)

    @extend_schema(request=ProfileUpdateSerializer, responses={200: UserSerializer})
    def patch(self, request):
        serializer = ProfileUpdateSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(UserSerializer(request.user, context={"request": request}).data)


@extend_schema(
    tags=["Auth"],
    summary="Change password",
    request=ChangePasswordSerializer,
    responses={200: OpenApiResponse(description="Password updated")},
)
class ChangePasswordAPIView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ChangePasswordSerializer

    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({"success": True, "message": "Password updated successfully."})


@extend_schema(tags=["Users"])
class UserViewSet(viewsets.ModelViewSet):
    """Employee administration. Admin-only, apart from the ``roles`` helper."""

    queryset = User.objects.all().order_by("username")
    permission_classes = [IsAuthenticated, IsAdminRole]
    filterset_fields = ["role", "is_active"]
    search_fields = ["username", "email", "first_name", "last_name", "department"]
    ordering_fields = ["username", "date_joined", "last_login", "role"]

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return UserWriteSerializer
        return UserSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        search = self.request.query_params.get("q")
        if search:
            qs = qs.filter(
                Q(username__icontains=search)
                | Q(email__icontains=search)
                | Q(first_name__icontains=search)
                | Q(last_name__icontains=search)
            )
        return qs

    def perform_destroy(self, instance):
        # Deactivate rather than delete: challans, stock movements and
        # follow-ups all reference the user for audit purposes.
        instance.is_active = False
        instance.save(update_fields=["is_active", "updated_at"])

    @extend_schema(
        summary="List available roles",
        responses={200: RoleSerializer(many=True)},
    )
    @action(detail=False, methods=["get"], permission_classes=[IsAuthenticated])
    def roles(self, request):
        return Response(RoleSerializer.all_roles())

    @extend_schema(summary="Activate a user", request=None, responses={200: UserSerializer})
    @action(detail=True, methods=["post"])
    def activate(self, request, pk=None):
        user = self.get_object()
        user.is_active = True
        user.save(update_fields=["is_active", "updated_at"])
        return Response(UserSerializer(user, context={"request": request}).data)

    @extend_schema(summary="Deactivate a user", request=None, responses={200: UserSerializer})
    @action(detail=True, methods=["post"])
    def deactivate(self, request, pk=None):
        user = self.get_object()
        if user.pk == request.user.pk:
            return Response(
                {
                    "success": False,
                    "error": {
                        "code": "cannot_deactivate_self",
                        "message": "You cannot deactivate your own account.",
                        "details": {},
                    },
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        user.is_active = False
        user.save(update_fields=["is_active", "updated_at"])
        return Response(UserSerializer(user, context={"request": request}).data)


__all__ = [
    "LoginAPIView",
    "RefreshAPIView",
    "LogoutAPIView",
    "SessionTokenAPIView",
    "MeAPIView",
    "ChangePasswordAPIView",
    "UserViewSet",
    "Role",
]
