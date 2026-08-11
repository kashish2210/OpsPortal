"""Serializers for the authentication and user-management APIs."""

from django.contrib.auth import authenticate, get_user_model, password_validation
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken

from .models import Role

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    """Public representation of an employee account."""

    role_display = serializers.CharField(source="get_role_display", read_only=True)
    full_name = serializers.CharField(source="display_name", read_only=True)
    initials = serializers.CharField(read_only=True)
    avatar_url = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "full_name",
            "initials",
            "role",
            "role_display",
            "phone",
            "department",
            "avatar_url",
            "is_active",
            "is_staff",
            "is_superuser",
            "is_email_verified",
            "last_login",
            "date_joined",
        )
        read_only_fields = (
            "id",
            "is_staff",
            "is_superuser",
            "is_email_verified",
            "last_login",
            "date_joined",
        )

    def get_avatar_url(self, obj):
        if not obj.avatar:
            return None
        request = self.context.get("request")
        url = obj.avatar.url
        return request.build_absolute_uri(url) if request else url


class UserWriteSerializer(serializers.ModelSerializer):
    """Admin-side create/update, including the initial password."""

    password = serializers.CharField(
        write_only=True, required=False, allow_blank=False, style={"input_type": "password"}
    )

    class Meta:
        model = User
        fields = (
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "role",
            "phone",
            "department",
            "is_active",
            "password",
        )

    def validate_email(self, value):
        value = value.lower().strip()
        qs = User.objects.filter(email__iexact=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError(_("An account with this e-mail already exists."))
        return value

    def validate_password(self, value):
        password_validation.validate_password(value)
        return value

    def validate(self, attrs):
        if self.instance is None and not attrs.get("password"):
            raise serializers.ValidationError(
                {"password": [_("A password is required when creating a user.")]}
            )
        return attrs

    def create(self, validated_data):
        password = validated_data.pop("password")
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user

    def update(self, instance, validated_data):
        password = validated_data.pop("password", None)
        for field, value in validated_data.items():
            setattr(instance, field, value)
        if password:
            instance.set_password(password)
        instance.save()
        return instance

    def to_representation(self, instance):
        return UserSerializer(instance, context=self.context).data


class ProfileUpdateSerializer(serializers.ModelSerializer):
    """What a user may change about *themselves* (role is deliberately absent)."""

    class Meta:
        model = User
        fields = ("first_name", "last_name", "phone", "department", "avatar")


class LoginSerializer(serializers.Serializer):
    """Username *or* e-mail plus password -> JWT pair."""

    username = serializers.CharField(
        help_text=_("Username or e-mail address."), trim_whitespace=True
    )
    password = serializers.CharField(write_only=True, style={"input_type": "password"})

    default_error_messages = {
        "invalid_credentials": _("Invalid credentials. Please check and try again."),
        "inactive": _("This account has been deactivated. Contact an administrator."),
    }

    def validate(self, attrs):
        request = self.context.get("request")
        user = authenticate(
            request=request, username=attrs["username"], password=attrs["password"]
        )
        if user is None:
            # Distinguish "wrong password" from "deactivated account" without
            # leaking which usernames exist.
            candidate = User.objects.filter(
                username__iexact=attrs["username"]
            ).first() or User.objects.filter(email__iexact=attrs["username"]).first()
            if candidate is not None and not candidate.is_active:
                self.fail("inactive")
            self.fail("invalid_credentials")
        if not user.is_active:
            self.fail("inactive")
        attrs["user"] = user
        return attrs

    def to_representation(self, instance):
        return instance


class TokenPairSerializer(serializers.Serializer):
    """Documents the login/refresh response shape for the OpenAPI schema."""

    access = serializers.CharField()
    refresh = serializers.CharField()
    user = UserSerializer(read_only=True)


def build_token_response(user, context=None):
    refresh = RefreshToken.for_user(user)
    refresh["role"] = user.role
    refresh["username"] = user.username
    access = refresh.access_token
    access["role"] = user.role
    access["username"] = user.username
    return {
        "access": str(access),
        "refresh": str(refresh),
        "user": UserSerializer(user, context=context or {}).data,
    }


class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField(help_text=_("The refresh token to blacklist."))


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True, style={"input_type": "password"})
    new_password = serializers.CharField(write_only=True, style={"input_type": "password"})

    def validate_old_password(self, value):
        user = self.context["request"].user
        if not user.check_password(value):
            raise serializers.ValidationError(_("Your current password is incorrect."))
        return value

    def validate_new_password(self, value):
        password_validation.validate_password(value, self.context["request"].user)
        return value

    def save(self, **kwargs):
        user = self.context["request"].user
        user.set_password(self.validated_data["new_password"])
        user.save(update_fields=["password", "updated_at"])
        return user


class RoleSerializer(serializers.Serializer):
    """Feeds role dropdowns in the SPA."""

    value = serializers.CharField()
    label = serializers.CharField()

    @staticmethod
    def all_roles():
        return [{"value": value, "label": label} for value, label in Role.choices]
