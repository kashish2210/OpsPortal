"""User model and role definitions.

The portal is used by four internal teams. Roles are stored on the user record
itself (a single role per user) which keeps permission checks cheap and the
admin UI simple - matching how a small distribution company actually works.
"""

from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class Role(models.TextChoices):
    ADMIN = "ADMIN", _("Admin")
    SALES = "SALES", _("Sales")
    WAREHOUSE = "WAREHOUSE", _("Warehouse")
    ACCOUNTS = "ACCOUNTS", _("Accounts")


#: Convenience groupings used by the viewsets' ``read_roles`` / ``write_roles``.
ALL_ROLES = {Role.ADMIN, Role.SALES, Role.WAREHOUSE, Role.ACCOUNTS}


class UserManager(BaseUserManager):
    """Manager that normalises e-mail and requires it on every account."""

    use_in_migrations = True

    def _create_user(self, username, email, password, **extra_fields):
        if not username:
            raise ValueError("A username is required.")
        if not email:
            raise ValueError("An e-mail address is required.")
        email = self.normalize_email(email).lower()
        user = self.model(username=username, email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, username, email=None, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        extra_fields.setdefault("role", Role.SALES)
        return self._create_user(username, email, password, **extra_fields)

    def create_superuser(self, username, email=None, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("role", Role.ADMIN)
        extra_fields.setdefault("is_email_verified", True)
        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")
        return self._create_user(username, email, password, **extra_fields)


class User(AbstractUser):
    """Internal employee account."""

    email = models.EmailField(
        _("e-mail address"),
        unique=True,
        help_text=_("Used to sign in and to receive password-reset e-mails."),
    )
    role = models.CharField(
        _("role"),
        max_length=20,
        choices=Role.choices,
        default=Role.SALES,
        db_index=True,
        help_text=_("Controls which modules this employee can read and edit."),
    )
    phone = models.CharField(_("phone"), max_length=20, blank=True)
    department = models.CharField(_("department"), max_length=80, blank=True)
    avatar = models.ImageField(_("avatar"), upload_to="avatars/", blank=True, null=True)

    is_email_verified = models.BooleanField(_("e-mail verified"), default=False)
    email_verified_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = UserManager()

    REQUIRED_FIELDS = ["email"]

    class Meta:
        ordering = ("username",)
        verbose_name = _("user")
        verbose_name_plural = _("users")
        indexes = [models.Index(fields=["role", "is_active"])]

    def __str__(self):
        return f"{self.get_full_name() or self.username} ({self.get_role_display()})"

    # -- role helpers -------------------------------------------------------
    @property
    def is_admin_role(self):
        return self.role == Role.ADMIN or self.is_superuser

    @property
    def is_sales(self):
        return self.role == Role.SALES

    @property
    def is_warehouse(self):
        return self.role == Role.WAREHOUSE

    @property
    def is_accounts(self):
        return self.role == Role.ACCOUNTS

    @property
    def display_name(self):
        return self.get_full_name() or self.username

    @property
    def initials(self):
        parts = [p for p in (self.first_name, self.last_name) if p]
        if parts:
            return "".join(p[0] for p in parts).upper()[:2]
        return self.username[:2].upper()

    def save(self, *args, **kwargs):
        if self.email:
            self.email = self.email.lower().strip()
        super().save(*args, **kwargs)

    def mark_email_verified(self):
        self.is_email_verified = True
        self.email_verified_at = timezone.now()
        self.save(update_fields=["is_email_verified", "email_verified_at", "updated_at"])
