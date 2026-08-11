"""E-mailed links must be correct regardless of how the request arrived.

Behind a reverse proxy the Host header is easy to get wrong - nginx's ``$host``
drops the port, for instance - and a broken link in a password-reset e-mail is
invisible until a user complains. These tests pin the behaviour.
"""

import re

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse

from .emails import send_verification_email

User = get_user_model()

RESET_LINK = re.compile(r"https?://[^\s]*?/accounts/password/reset/key/[^\s]+")
VERIFY_LINK = re.compile(r"https?://[^\s]*?/accounts/email/confirm/[^\s]+")


class PasswordResetLinkTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("riya", "riya@example.com", "Str0ng!pass")

    def _request_reset(self, **headers):
        mail.outbox.clear()
        self.client.post(reverse("accounts:password_reset"), {"email": "riya@example.com"}, **headers)
        self.assertEqual(len(mail.outbox), 1)
        match = RESET_LINK.search(mail.outbox[0].body)
        self.assertIsNotNone(match, f"no reset link in:\n{mail.outbox[0].body}")
        return match.group(0)

    @override_settings(FRONTEND_URL="http://localhost:8081")
    def test_link_keeps_a_non_default_port(self):
        """The regression this guards: nginx $host produced http://localhost/..."""
        link = self._request_reset()
        self.assertTrue(link.startswith("http://localhost:8081/accounts/password/reset/key/"), link)

    @override_settings(FRONTEND_URL="https://opsportal.example.com")
    def test_link_uses_the_configured_https_origin(self):
        link = self._request_reset()
        self.assertTrue(link.startswith("https://opsportal.example.com/accounts/"), link)

    @override_settings(
        FRONTEND_URL="https://opsportal.example.com",
        ALLOWED_HOSTS=["localhost", "testserver"],
    )
    def test_an_unknown_host_is_rejected_before_any_mail_is_sent(self):
        """First line of defence: ALLOWED_HOSTS refuses the request outright."""
        mail.outbox.clear()
        response = self.client.post(
            reverse("accounts:password_reset"),
            {"email": "riya@example.com"},
            HTTP_HOST="evil.example.net",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(len(mail.outbox), 0, "no e-mail may be sent for a rejected host")

    @override_settings(
        FRONTEND_URL="https://opsportal.example.com",
        ALLOWED_HOSTS=["localhost", "testserver", "evil.example.net"],
    )
    def test_the_link_ignores_the_host_header_even_when_it_is_allowed(self):
        """Second line of defence: the link comes from config, not the request."""
        link = self._request_reset(HTTP_HOST="evil.example.net")
        self.assertNotIn("evil.example.net", link)
        self.assertTrue(link.startswith("https://opsportal.example.com/"), link)

    @override_settings(FRONTEND_URL="http://localhost:8081")
    def test_subject_uses_the_site_name_not_the_host(self):
        mail.outbox.clear()
        self.client.post(reverse("accounts:password_reset"), {"email": "riya@example.com"})
        self.assertIn("OpsPortal", mail.outbox[0].subject)

    @override_settings(FRONTEND_URL="http://localhost:8081")
    def test_the_emailed_link_actually_works(self):
        link = self._request_reset()
        path = "/" + link.split("/", 3)[3]
        response = self.client.get(path, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "registration/password_reset_confirm.html")

    @override_settings(FRONTEND_URL="http://localhost:8081")
    def test_both_plain_text_and_html_bodies_carry_the_link(self):
        self._request_reset()
        message = mail.outbox[0]

        # `alternatives` is a list of (content, mimetype) pairs, not a mapping.
        html = next(
            (content for content, mimetype in message.alternatives if mimetype == "text/html"),
            "",
        )
        self.assertRegex(message.body, RESET_LINK)
        self.assertIn("localhost:8081", html)


class VerificationLinkTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("imran", "imran@example.com", "Str0ng!pass")

    @override_settings(FRONTEND_URL="http://localhost:8081")
    def test_verification_link_keeps_the_port(self):
        mail.outbox.clear()
        self.assertTrue(send_verification_email(self.user))

        match = VERIFY_LINK.search(mail.outbox[0].body)
        self.assertIsNotNone(match, mail.outbox[0].body)
        self.assertTrue(match.group(0).startswith("http://localhost:8081/accounts/email/confirm/"))

    @override_settings(FRONTEND_URL="https://opsportal.example.com")
    def test_verification_link_uses_the_configured_origin(self):
        mail.outbox.clear()
        send_verification_email(self.user)
        self.assertIn("https://opsportal.example.com/accounts/email/confirm/", mail.outbox[0].body)

    @override_settings(FRONTEND_URL="http://localhost:8081")
    def test_the_verification_link_actually_verifies(self):
        mail.outbox.clear()
        send_verification_email(self.user)
        link = VERIFY_LINK.search(mail.outbox[0].body).group(0)
        path = "/" + link.split("/", 3)[3]

        self.client.post(path)
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_email_verified)
