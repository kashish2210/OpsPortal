"""REST routes for authentication (mounted at ``/api/auth/``)."""

from django.urls import path

from . import api_views

urlpatterns = [
    path("login/", api_views.LoginAPIView.as_view(), name="api-login"),
    path("refresh/", api_views.RefreshAPIView.as_view(), name="api-token-refresh"),
    path("logout/", api_views.LogoutAPIView.as_view(), name="api-logout"),
    path("me/", api_views.MeAPIView.as_view(), name="api-me"),
    path(
        "change-password/",
        api_views.ChangePasswordAPIView.as_view(),
        name="api-change-password",
    ),
    path(
        "session-token/",
        api_views.SessionTokenAPIView.as_view(),
        name="api-session-token",
    ),
]
