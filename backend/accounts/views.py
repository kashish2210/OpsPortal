"""Server-rendered authentication pages.

These are plain ``django.contrib.auth`` views wearing the hand-drawn theme.
They cover the complete account lifecycle:

    login / logout / signup (+ closed) / profile
    password change / set / reset (request -> sent -> confirm -> done)
    e-mail management / confirmation / verification-sent / verification-required
    account inactive

Once signed in, the *Open OpsPortal* button on the profile page hands the
session over to the React SPA, which exchanges it for a JWT pair via
``POST /api/auth/session-token/``.
"""

from urllib.parse import urlparse

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model, update_session_auth_hash
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponseRedirect
from django.shortcuts import redirect, render
from django.urls import reverse, reverse_lazy
from django.utils.decorators import method_decorator
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from django.views.generic import FormView, TemplateView, View

from .emails import send_verification_email
from .forms import (
    EmailChangeForm,
    LoginForm,
    ProfileForm,
    SignupForm,
    SketchPasswordChangeForm,
    SketchPasswordResetForm,
    SketchSetPasswordForm,
)
from .tokens import email_verification_token

User = get_user_model()


# ---------------------------------------------------------------------------
# Login / logout
# ---------------------------------------------------------------------------
class LoginView(auth_views.LoginView):
    template_name = "registration/login.html"
    authentication_form = LoginForm
    redirect_authenticated_user = True

    def form_valid(self, form):
        response = super().form_valid(form)
        if settings.REQUIRE_EMAIL_VERIFICATION and not form.get_user().is_email_verified:
            # Signed in, but parked on the "verify your address" wall so the
            # protected pages stay closed until they confirm.
            return redirect("accounts:verified_email_required")
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["signup_url"] = reverse("accounts:signup")
        return context


class LogoutView(auth_views.LogoutView):
    """Django >= 5 only accepts POST for logout; the template posts a form."""

    template_name = "registration/logged_out.html"
    next_page = None
    # LogoutView allows POST only; re-enable GET so a stray link shows the
    # confirmation page instead of a 405.
    http_method_names = ["get", "post", "options"]

    def get(self, request, *args, **kwargs):
        return render(request, "registration/logout_confirm.html")


# ---------------------------------------------------------------------------
# Signup
# ---------------------------------------------------------------------------
@method_decorator([never_cache, csrf_protect], name="dispatch")
class SignupView(FormView):
    template_name = "registration/signup.html"
    form_class = SignupForm
    success_url = reverse_lazy("accounts:profile")

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect("accounts:profile")
        if not settings.SIGNUP_OPEN:
            return render(request, "registration/signup_closed.html", status=403)
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["login_url"] = reverse("accounts:login")
        return context

    def form_valid(self, form):
        user = form.save()
        send_verification_email(user, self.request)

        if settings.REQUIRE_EMAIL_VERIFICATION:
            self.request.session["pending_verification_email"] = user.email
            return redirect("accounts:verification_sent")

        from django.contrib.auth import login

        login(self.request, user, backend="accounts.backends.UsernameOrEmailBackend")
        messages.success(
            self.request,
            f"Welcome aboard, {user.display_name}! Your account was created with the "
            "Sales role - an administrator can change it from the Users screen.",
        )
        return super().form_valid(form)


class SignupClosedView(TemplateView):
    template_name = "registration/signup_closed.html"


# ---------------------------------------------------------------------------
# Password change / set
# ---------------------------------------------------------------------------
class PasswordChangeView(auth_views.PasswordChangeView):
    template_name = "registration/password_change_form.html"
    form_class = SketchPasswordChangeForm
    success_url = reverse_lazy("accounts:password_change_done")


class PasswordChangeDoneView(auth_views.PasswordChangeDoneView):
    template_name = "registration/password_change_done.html"


class PasswordSetView(LoginRequiredMixin, FormView):
    """For accounts created without a usable password (e.g. seeded/imported)."""

    template_name = "registration/password_set.html"
    form_class = SketchSetPasswordForm
    success_url = reverse_lazy("accounts:password_change_done")

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and request.user.has_usable_password():
            return redirect("accounts:password_change")
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        form.save()
        update_session_auth_hash(self.request, form.user)
        messages.success(self.request, "Your password has been set.")
        return super().form_valid(form)


# ---------------------------------------------------------------------------
# Password reset (4 steps)
# ---------------------------------------------------------------------------
class PasswordResetView(auth_views.PasswordResetView):
    template_name = "registration/password_reset_form.html"
    email_template_name = "registration/password_reset_email.txt"
    html_email_template_name = "registration/password_reset_email.html"
    subject_template_name = "registration/password_reset_subject.txt"
    form_class = SketchPasswordResetForm
    success_url = reverse_lazy("accounts:password_reset_done")

    @property
    def extra_email_context(self):
        """Build the reset link from ``FRONTEND_URL`` rather than the Host header.

        Django would otherwise derive the domain from the incoming request,
        which is fragile behind a reverse proxy (a misconfigured ``Host``
        header silently produces links pointing at the wrong origin, or drops
        the port). Deriving it from configuration makes the link correct no
        matter how the request arrived.
        """
        parsed = urlparse(settings.FRONTEND_URL)
        return {
            "site_name": settings.SITE_NAME,
            "domain": parsed.netloc or self.request.get_host(),
            "protocol": parsed.scheme or ("https" if self.request.is_secure() else "http"),
        }

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["login_url"] = reverse("accounts:login")
        return context


class PasswordResetDoneView(auth_views.PasswordResetDoneView):
    template_name = "registration/password_reset_done.html"


class PasswordResetConfirmView(auth_views.PasswordResetConfirmView):
    template_name = "registration/password_reset_confirm.html"
    form_class = SketchSetPasswordForm
    success_url = reverse_lazy("accounts:password_reset_complete")


class PasswordResetCompleteView(auth_views.PasswordResetCompleteView):
    template_name = "registration/password_reset_complete.html"


# ---------------------------------------------------------------------------
# E-mail address management & verification
# ---------------------------------------------------------------------------
class EmailManageView(LoginRequiredMixin, FormView):
    template_name = "registration/email.html"
    form_class = EmailChangeForm
    success_url = reverse_lazy("accounts:email")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def post(self, request, *args, **kwargs):
        # The template exposes two buttons: change the address, or re-send the
        # verification link for the current one.
        if "action_resend" in request.POST:
            if request.user.is_email_verified:
                messages.info(request, "This address is already verified.")
            elif send_verification_email(request.user, request):
                messages.success(request, f"Verification e-mail sent to {request.user.email}.")
            else:
                messages.error(request, "We could not send the verification e-mail. Try again later.")
            return redirect(self.success_url)
        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        user = self.request.user
        user.email = form.cleaned_data["email"]
        user.is_email_verified = False
        user.email_verified_at = None
        user.save(update_fields=["email", "is_email_verified", "email_verified_at", "updated_at"])
        send_verification_email(user, self.request)
        messages.success(
            self.request,
            f"Your e-mail address is now {user.email}. We have sent a confirmation link to it.",
        )
        return super().form_valid(form)


class EmailConfirmView(View):
    """Landing page for the link in the verification e-mail.

    GET shows a confirm button (so link scanners in mail clients cannot
    silently verify the address); POST performs the verification.
    """

    template_name = "registration/email_confirm.html"

    def _load_user(self, uidb64, token):
        try:
            uid = force_str(urlsafe_base64_decode(uidb64))
            user = User.objects.get(pk=uid)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            return None
        if not email_verification_token.check_token(user, token):
            return None
        return user

    def get(self, request, uidb64, token):
        user = self._load_user(uidb64, token)
        return render(
            request,
            self.template_name,
            {"confirmation_user": user, "valid": user is not None},
        )

    def post(self, request, uidb64, token):
        user = self._load_user(uidb64, token)
        if user is None:
            return render(
                request, self.template_name, {"confirmation_user": None, "valid": False}, status=400
            )
        user.mark_email_verified()
        messages.success(request, f"{user.email} is now confirmed.")
        if request.user.is_authenticated:
            return redirect("accounts:profile")
        return redirect("accounts:login")


class VerificationSentView(TemplateView):
    template_name = "registration/verification_sent.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["pending_email"] = self.request.session.get("pending_verification_email")
        return context


class VerifiedEmailRequiredView(LoginRequiredMixin, TemplateView):
    template_name = "registration/verified_email_required.html"

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and request.user.is_email_verified:
            return redirect("accounts:profile")
        return super().dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        if send_verification_email(request.user, request):
            messages.success(request, f"Verification e-mail re-sent to {request.user.email}.")
        else:
            messages.error(request, "We could not send the verification e-mail. Try again later.")
        return redirect("accounts:verified_email_required")


class AccountInactiveView(TemplateView):
    template_name = "registration/account_inactive.html"


# ---------------------------------------------------------------------------
# Profile / SPA handoff
# ---------------------------------------------------------------------------
class ProfileView(LoginRequiredMixin, FormView):
    """Post-login landing page and the bridge into the React application."""

    template_name = "registration/profile.html"
    form_class = ProfileForm
    success_url = reverse_lazy("accounts:profile")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["instance"] = self.request.user
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["app_url"] = f"{settings.FRONTEND_URL}/auth/handoff"
        return context

    def form_valid(self, form):
        form.save()
        messages.success(self.request, "Profile updated.")
        return super().form_valid(form)


@login_required
def spa_handoff(request):
    """Convenience redirect: Django session -> React app."""
    return HttpResponseRedirect(f"{settings.FRONTEND_URL}/auth/handoff")
