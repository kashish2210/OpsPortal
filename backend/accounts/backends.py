"""Authentication backend allowing sign-in with username *or* e-mail."""

from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
from django.db.models import Q


class UsernameOrEmailBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        User = get_user_model()
        identifier = username or kwargs.get("email")
        if identifier is None or password is None:
            return None

        try:
            user = User.objects.get(
                Q(username__iexact=identifier.strip()) | Q(email__iexact=identifier.strip())
            )
        except User.DoesNotExist:
            # Run the hasher anyway so timing does not leak whether the
            # account exists.
            User().set_password(password)
            return None
        except User.MultipleObjectsReturned:
            # Extremely unlikely (both fields are unique) but be deterministic.
            user = (
                User.objects.filter(
                    Q(username__iexact=identifier.strip()) | Q(email__iexact=identifier.strip())
                )
                .order_by("id")
                .first()
            )

        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
