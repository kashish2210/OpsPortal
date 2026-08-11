"""Forms backing the server-rendered (Django auth) pages.

The templates render fields manually where possible, but Django's built-in
auth views hand us bound forms, so every widget gets the placeholder/autocomplete
attributes here to keep the hand-drawn UI consistent.
"""

import base64
import binascii
import uuid

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import (
    AuthenticationForm,
    PasswordChangeForm,
    PasswordResetForm,
    SetPasswordForm,
    UserCreationForm,
)
from django.core.files.base import ContentFile
from django.utils.translation import gettext_lazy as _

User = get_user_model()

#: Guard against someone posting a multi-megabyte data URL.
MAX_AVATAR_BYTES = 3 * 1024 * 1024


def decode_data_url(data_url, *, field_label="image"):
    """Turn a ``data:image/jpeg;base64,...`` string into a Django file.

    Returns ``None`` for empty input. Raises ``ValidationError`` for anything
    that is not a plausible image data URL.
    """
    if not data_url:
        return None
    try:
        header, payload = data_url.split(";base64,", 1)
    except ValueError:
        raise forms.ValidationError(_("The %(label)s could not be read.") % {"label": field_label})

    mime = header.split(":")[-1].lower()
    extension = {
        "image/jpeg": "jpg",
        "image/jpg": "jpg",
        "image/png": "png",
        "image/webp": "webp",
    }.get(mime)
    if extension is None:
        raise forms.ValidationError(_("Only JPEG, PNG or WebP images are supported."))

    try:
        raw = base64.b64decode(payload, validate=True)
    except (binascii.Error, ValueError):
        raise forms.ValidationError(_("The %(label)s could not be decoded.") % {"label": field_label})

    if len(raw) > MAX_AVATAR_BYTES:
        raise forms.ValidationError(_("The %(label)s must be smaller than 3 MB.") % {"label": field_label})

    return ContentFile(raw, name=f"{uuid.uuid4().hex}.{extension}")


class SketchFormMixin:
    """Applies the shared placeholder/CSS treatment to every widget."""

    placeholders: dict = {}

    def _decorate(self):
        for name, field in self.fields.items():
            widget = field.widget
            if isinstance(widget, (forms.CheckboxInput, forms.FileInput)):
                continue
            placeholder = self.placeholders.get(name)
            if placeholder:
                widget.attrs.setdefault("placeholder", placeholder)
            css = widget.attrs.get("class", "")
            widget.attrs["class"] = f"{css} sketch-input".strip()


class LoginForm(SketchFormMixin, AuthenticationForm):
    """Accepts a username *or* an e-mail address (see ``accounts.backends``)."""

    placeholders = {
        "username": "you@company.com or username",
        "password": "•••••••••",
    }
    error_messages = {
        **AuthenticationForm.error_messages,
        "invalid_login": _(
            "Those credentials did not match any account. "
            "Check the username / e-mail and password and try again."
        ),
        "inactive": _("This account has been deactivated. Please contact an administrator."),
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].label = _("Username or e-mail")
        self.fields["username"].widget.attrs["autocomplete"] = "username"
        self.fields["username"].widget.attrs["autofocus"] = True
        self.fields["password"].widget.attrs["autocomplete"] = "current-password"
        self._decorate()


class SignupForm(SketchFormMixin, UserCreationForm):
    """Self-service registration.

    New accounts land on the ``Sales`` role; an administrator promotes them
    afterwards from the Users screen (or Django admin).
    """

    placeholders = {
        "username": "e.g. r.sharma",
        "email": "you@company.com",
        "first_name": "Riya",
        "last_name": "Sharma",
        "phone": "+91 98765 43210",
        "department": "Sales / Warehouse / Accounts",
        "password1": "at least 8 characters",
        "password2": "repeat the password",
    }

    first_name = forms.CharField(label=_("First name"), max_length=150, required=True)
    last_name = forms.CharField(label=_("Last name"), max_length=150, required=False)
    phone = forms.CharField(label=_("Phone"), max_length=20, required=False)
    department = forms.CharField(label=_("Department"), max_length=80, required=False)

    # Populated by the Cropper.js widget in the template.
    avatar_base64 = forms.CharField(required=False, widget=forms.HiddenInput())

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "email", "first_name", "last_name", "phone", "department")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["email"].required = True
        self.fields["username"].help_text = _("Letters, digits and @ . + - _ only.")
        self.fields["email"].widget.attrs["autocomplete"] = "email"
        self._decorate()

    def clean_email(self):
        email = (self.cleaned_data.get("email") or "").lower().strip()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError(_("An account with this e-mail address already exists."))
        return email

    def clean_avatar_base64(self):
        return decode_data_url(self.cleaned_data.get("avatar_base64"), field_label=_("profile picture"))

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        user.first_name = self.cleaned_data.get("first_name", "")
        user.last_name = self.cleaned_data.get("last_name", "")
        user.phone = self.cleaned_data.get("phone", "")
        user.department = self.cleaned_data.get("department", "")
        if commit:
            user.save()
            avatar = self.cleaned_data.get("avatar_base64")
            if avatar:
                user.avatar.save(avatar.name, avatar, save=True)
        return user


class SketchPasswordResetForm(SketchFormMixin, PasswordResetForm):
    placeholders = {"email": "you@company.com"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["email"].label = _("E-mail address")
        self._decorate()


class SketchSetPasswordForm(SketchFormMixin, SetPasswordForm):
    placeholders = {"new_password1": "at least 8 characters", "new_password2": "repeat it"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._decorate()


class SketchPasswordChangeForm(SketchFormMixin, PasswordChangeForm):
    placeholders = {
        "old_password": "your current password",
        "new_password1": "at least 8 characters",
        "new_password2": "repeat it",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._decorate()


class EmailChangeForm(SketchFormMixin, forms.Form):
    """Backs the "E-mail addresses" screen."""

    placeholders = {"email": "you@company.com"}
    email = forms.EmailField(label=_("New e-mail address"))

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        self._decorate()

    def clean_email(self):
        email = self.cleaned_data["email"].lower().strip()
        if email == (self.user.email or "").lower():
            raise forms.ValidationError(_("This is already your e-mail address."))
        if User.objects.filter(email__iexact=email).exclude(pk=self.user.pk).exists():
            raise forms.ValidationError(_("Another account already uses this e-mail address."))
        return email


class ProfileForm(SketchFormMixin, forms.ModelForm):
    """Lets a signed-in employee maintain their own details."""

    placeholders = {
        "first_name": "Riya",
        "last_name": "Sharma",
        "phone": "+91 98765 43210",
        "department": "Sales",
    }
    avatar_base64 = forms.CharField(required=False, widget=forms.HiddenInput())

    class Meta:
        model = User
        fields = ("first_name", "last_name", "phone", "department")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._decorate()

    def clean_avatar_base64(self):
        return decode_data_url(self.cleaned_data.get("avatar_base64"), field_label=_("profile picture"))

    def save(self, commit=True):
        user = super().save(commit=commit)
        avatar = self.cleaned_data.get("avatar_base64")
        if avatar and commit:
            user.avatar.save(avatar.name, avatar, save=True)
        return user
