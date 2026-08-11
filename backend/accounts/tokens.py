"""Signed, time-limited token used for e-mail address confirmation.

Reuses Django's password-reset token machinery so we get the same rotation
guarantees: the hash includes the user's current e-mail and verification flag,
so a token is invalidated as soon as it is used or the address changes.
"""

from django.contrib.auth.tokens import PasswordResetTokenGenerator


class EmailVerificationTokenGenerator(PasswordResetTokenGenerator):
    key_salt = "accounts.EmailVerificationTokenGenerator"

    def _make_hash_value(self, user, timestamp):
        return f"{user.pk}{user.email}{user.is_email_verified}{timestamp}"


email_verification_token = EmailVerificationTokenGenerator()
