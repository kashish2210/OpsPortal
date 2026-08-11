"""Transactional e-mail helpers."""

import logging

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from .tokens import email_verification_token

logger = logging.getLogger("opsportal.accounts")


def build_absolute(request, path):
    """Absolute URL for a link we are about to put in an e-mail.

    Prefers the configured ``FRONTEND_URL`` over the request's Host header:
    behind a reverse proxy the header is easy to get wrong (``$host`` drops the
    port, for one), and a broken link in a verification e-mail is invisible
    until a user reports it.
    """
    base = (settings.FRONTEND_URL or "").rstrip("/")
    if base:
        return f"{base}{path}"
    if request is not None:
        return request.build_absolute_uri(path)
    return path


def send_verification_email(user, request=None):
    """E-mail the user a signed link that confirms their address."""
    if not user.email:
        return False

    uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
    token = email_verification_token.make_token(user)
    path = reverse("accounts:email_confirm", kwargs={"uidb64": uidb64, "token": token})
    context = {
        "user": user,
        "site_name": settings.SITE_NAME,
        "confirm_url": build_absolute(request, path),
    }

    subject = f"[{settings.SITE_NAME}] Confirm your e-mail address"
    text_body = render_to_string("emails/email_verification.txt", context)
    html_body = render_to_string("emails/email_verification.html", context)

    message = EmailMultiAlternatives(subject, text_body, settings.DEFAULT_FROM_EMAIL, [user.email])
    message.attach_alternative(html_body, "text/html")
    try:
        message.send(fail_silently=False)
    except Exception:  # pragma: no cover - depends on the SMTP provider
        logger.exception("Could not send verification e-mail to %s", user.email)
        return False
    return True
