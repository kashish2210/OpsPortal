"""Serializers for the Customer CRM module."""

from django.utils import timezone
from rest_framework import serializers

from .models import Customer, CustomerStatus, CustomerType, FollowUp, FollowUpChannel


class FollowUpSerializer(serializers.ModelSerializer):
    channel_display = serializers.CharField(source="get_channel_display", read_only=True)
    created_by_name = serializers.CharField(source="created_by.display_name", read_only=True, default=None)
    customer_name = serializers.CharField(source="customer.name", read_only=True)

    class Meta:
        model = FollowUp
        fields = (
            "id",
            "customer",
            "customer_name",
            "note",
            "channel",
            "channel_display",
            "next_follow_up_date",
            "created_by",
            "created_by_name",
            "created_at",
        )
        read_only_fields = ("id", "created_by", "created_at")

    def validate_note(self, value):
        value = value.strip()
        if len(value) < 3:
            raise serializers.ValidationError("Please write a slightly more descriptive note.")
        return value

    def validate_next_follow_up_date(self, value):
        if value and value < timezone.localdate():
            raise serializers.ValidationError("The next follow-up date cannot be in the past.")
        return value


class CustomerListSerializer(serializers.ModelSerializer):
    """Trimmed payload for the customers table."""

    customer_type_display = serializers.CharField(source="get_customer_type_display", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    is_follow_up_due = serializers.BooleanField(read_only=True)

    class Meta:
        model = Customer
        fields = (
            "id",
            "code",
            "name",
            "business_name",
            "mobile",
            "email",
            "customer_type",
            "customer_type_display",
            "status",
            "status_display",
            "city",
            "follow_up_date",
            "is_follow_up_due",
            "created_at",
        )


class CustomerSerializer(serializers.ModelSerializer):
    """Full customer record used by the detail page and create/update calls."""

    customer_type_display = serializers.CharField(source="get_customer_type_display", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    full_address = serializers.CharField(read_only=True)
    is_follow_up_due = serializers.BooleanField(read_only=True)
    created_by_name = serializers.CharField(source="created_by.display_name", read_only=True, default=None)
    follow_up_count = serializers.IntegerField(read_only=True)
    challan_count = serializers.IntegerField(read_only=True)
    recent_follow_ups = serializers.SerializerMethodField()

    class Meta:
        model = Customer
        fields = (
            "id",
            "code",
            "name",
            "business_name",
            "mobile",
            "email",
            "gst_number",
            "customer_type",
            "customer_type_display",
            "status",
            "status_display",
            "address",
            "city",
            "state",
            "pincode",
            "full_address",
            "credit_limit",
            "follow_up_date",
            "is_follow_up_due",
            "notes",
            "follow_up_count",
            "challan_count",
            "recent_follow_ups",
            "created_by",
            "created_by_name",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "code", "created_by", "created_at", "updated_at")

    def get_recent_follow_ups(self, obj):
        # Only populated on the detail endpoint (prefetched by the viewset).
        if not self.context.get("include_follow_ups"):
            return None
        return FollowUpSerializer(obj.follow_ups.all()[:10], many=True).data

    # -- field level validation -------------------------------------------
    def validate_name(self, value):
        value = value.strip()
        if len(value) < 2:
            raise serializers.ValidationError("Customer name must be at least 2 characters.")
        return value

    def validate_mobile(self, value):
        value = value.strip()
        digits = "".join(ch for ch in value if ch.isdigit())
        if len(digits) < 7:
            raise serializers.ValidationError("A mobile number needs at least 7 digits.")
        return value

    def validate_gst_number(self, value):
        return (value or "").upper().strip()

    def validate_follow_up_date(self, value):
        if value and value < timezone.localdate() and not self.instance:
            raise serializers.ValidationError("A new follow-up date cannot be in the past.")
        return value

    def validate(self, attrs):
        # Wholesalers and distributors invoice against a GSTIN, so require one.
        customer_type = attrs.get(
            "customer_type", getattr(self.instance, "customer_type", CustomerType.RETAIL)
        )
        gst = attrs.get("gst_number", getattr(self.instance, "gst_number", ""))
        if customer_type in (CustomerType.WHOLESALE, CustomerType.DISTRIBUTOR) and not gst:
            raise serializers.ValidationError(
                {"gst_number": ["A GST number is required for wholesale and distributor customers."]}
            )

        status_value = attrs.get("status", getattr(self.instance, "status", CustomerStatus.LEAD))
        follow_up = attrs.get("follow_up_date", getattr(self.instance, "follow_up_date", None))
        if status_value == CustomerStatus.LEAD and follow_up is None and self.instance is None:
            # Leads without a next action tend to be forgotten - nudge the user.
            raise serializers.ValidationError(
                {"follow_up_date": ["Set a follow-up date when creating a lead."]}
            )
        return attrs


class CustomerOptionSerializer(serializers.ModelSerializer):
    """Lightweight payload for the challan builder's customer picker."""

    label = serializers.SerializerMethodField()

    class Meta:
        model = Customer
        fields = ("id", "code", "name", "business_name", "mobile", "customer_type", "status", "label")

    def get_label(self, obj):
        return f"{obj.name} - {obj.mobile}" + (f" ({obj.business_name})" if obj.business_name else "")


class CustomerStatsSerializer(serializers.Serializer):
    total = serializers.IntegerField()
    leads = serializers.IntegerField()
    active = serializers.IntegerField()
    inactive = serializers.IntegerField()
    follow_ups_due = serializers.IntegerField()
    by_type = serializers.DictField(child=serializers.IntegerField())


CHOICES_PAYLOAD = {
    "customer_type": [{"value": value, "label": str(label)} for value, label in CustomerType.choices],
    "status": [{"value": value, "label": str(label)} for value, label in CustomerStatus.choices],
    "follow_up_channel": [{"value": value, "label": str(label)} for value, label in FollowUpChannel.choices],
}
