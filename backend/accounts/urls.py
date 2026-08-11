"""URLs for the server-rendered auth pages (mounted at ``/accounts/``)."""

from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    # -- session -----------------------------------------------------------
    path("login/", views.LoginView.as_view(), name="login"),
    path("logout/", views.LogoutView.as_view(), name="logout"),
    path("signup/", views.SignupView.as_view(), name="signup"),
    path("signup/closed/", views.SignupClosedView.as_view(), name="signup_closed"),
    path("profile/", views.ProfileView.as_view(), name="profile"),
    path("open-app/", views.spa_handoff, name="spa_handoff"),
    path("inactive/", views.AccountInactiveView.as_view(), name="account_inactive"),
    # -- password ----------------------------------------------------------
    path("password/change/", views.PasswordChangeView.as_view(), name="password_change"),
    path(
        "password/change/done/",
        views.PasswordChangeDoneView.as_view(),
        name="password_change_done",
    ),
    path("password/set/", views.PasswordSetView.as_view(), name="password_set"),
    path("password/reset/", views.PasswordResetView.as_view(), name="password_reset"),
    path(
        "password/reset/sent/",
        views.PasswordResetDoneView.as_view(),
        name="password_reset_done",
    ),
    path(
        "password/reset/key/<uidb64>/<token>/",
        views.PasswordResetConfirmView.as_view(),
        name="password_reset_confirm",
    ),
    path(
        "password/reset/complete/",
        views.PasswordResetCompleteView.as_view(),
        name="password_reset_complete",
    ),
    # -- e-mail ------------------------------------------------------------
    path("email/", views.EmailManageView.as_view(), name="email"),
    path(
        "email/confirm/<uidb64>/<token>/",
        views.EmailConfirmView.as_view(),
        name="email_confirm",
    ),
    path("email/sent/", views.VerificationSentView.as_view(), name="verification_sent"),
    path(
        "email/required/",
        views.VerifiedEmailRequiredView.as_view(),
        name="verified_email_required",
    ),
]
