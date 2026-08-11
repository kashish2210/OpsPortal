"""Serializers for the product & inventory module."""

from django.conf import settings
from rest_framework import serializers

from .models import (
    MovementReason,
    MovementType,
    Product,
    StockMovement,
    UnitOfMeasure,
)

#: Formats we accept for product photos.
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}


def validate_uploaded_image(uploaded):
    """Shared checks for product images: size and real content type."""
    if uploaded is None:
        return uploaded

    max_bytes = settings.MAX_UPLOAD_SIZE_BYTES
    if uploaded.size > max_bytes:
        raise serializers.ValidationError(
            f"The image is {uploaded.size / 1_048_576:.1f} MB; the limit is "
            f"{max_bytes // 1_048_576} MB."
        )

    # Django's ImageField already verifies the file really is an image via
    # Pillow; this narrows it to the formats we are willing to serve.
    content_type = getattr(uploaded, "content_type", None)
    if content_type and content_type.lower() not in ALLOWED_IMAGE_TYPES:
        raise serializers.ValidationError("Only JPEG, PNG or WebP images are supported.")
    return uploaded


class ImageUrlMixin:
    """Absolute URL for a product image (works for both local media and S3)."""

    def get_image_url(self, obj):
        if not obj.image:
            return None
        url = obj.image.url
        # S3 returns an absolute (often pre-signed) URL already.
        if url.startswith("http://") or url.startswith("https://"):
            return url
        request = self.context.get("request")
        return request.build_absolute_uri(url) if request else url


class ProductListSerializer(ImageUrlMixin, serializers.ModelSerializer):
    unit_display = serializers.CharField(source="get_unit_display", read_only=True)
    is_low_stock = serializers.BooleanField(read_only=True)
    is_out_of_stock = serializers.BooleanField(read_only=True)
    stock_value = serializers.DecimalField(max_digits=16, decimal_places=2, read_only=True)
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = (
            "id",
            "name",
            "sku",
            "category",
            "unit",
            "unit_display",
            "unit_price",
            "current_stock",
            "min_stock_alert",
            "location",
            "is_active",
            "is_low_stock",
            "is_out_of_stock",
            "stock_value",
            "image_url",
            "updated_at",
        )


class ProductSerializer(ImageUrlMixin, serializers.ModelSerializer):
    """Create / update / detail.

    ``current_stock`` is read-only everywhere: stock only ever moves through a
    :class:`StockMovement`. On create you may pass ``opening_stock`` and the
    viewset records it as an OPENING movement.
    """

    unit_display = serializers.CharField(source="get_unit_display", read_only=True)
    is_low_stock = serializers.BooleanField(read_only=True)
    is_out_of_stock = serializers.BooleanField(read_only=True)
    stock_value = serializers.DecimalField(max_digits=16, decimal_places=2, read_only=True)
    created_by_name = serializers.CharField(source="created_by.display_name", read_only=True, default=None)
    image_url = serializers.SerializerMethodField()
    opening_stock = serializers.IntegerField(
        write_only=True,
        required=False,
        min_value=0,
        help_text="Only honoured on create; recorded as an OPENING stock movement.",
    )

    class Meta:
        model = Product
        fields = (
            "id",
            "name",
            "sku",
            "category",
            "description",
            "unit",
            "unit_display",
            "unit_price",
            "hsn_code",
            "tax_rate",
            "current_stock",
            "opening_stock",
            "min_stock_alert",
            "location",
            "is_active",
            "is_low_stock",
            "is_out_of_stock",
            "stock_value",
            "image",
            "image_url",
            "created_by",
            "created_by_name",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "current_stock", "created_by", "created_at", "updated_at")
        extra_kwargs = {"image": {"write_only": True, "required": False}}

    def validate_image(self, value):
        return validate_uploaded_image(value)

    def validate_sku(self, value):
        value = value.upper().strip()
        if not value:
            raise serializers.ValidationError("SKU is required.")
        if len(value) < 2:
            raise serializers.ValidationError("SKU must be at least 2 characters.")
        qs = Product.objects.filter(sku__iexact=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("This SKU is already used by another product.")
        return value

    def validate_name(self, value):
        value = value.strip()
        if len(value) < 2:
            raise serializers.ValidationError("Product name must be at least 2 characters.")
        return value

    def validate_category(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Category is required.")
        return value

    def validate_unit_price(self, value):
        if value < 0:
            raise serializers.ValidationError("Unit price cannot be negative.")
        return value


class ProductOptionSerializer(serializers.ModelSerializer):
    """Slim payload for the challan line picker."""

    label = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = (
            "id",
            "name",
            "sku",
            "category",
            "unit",
            "unit_price",
            "current_stock",
            "location",
            "label",
        )

    def get_label(self, obj):
        return f"{obj.sku} - {obj.name}"


class StockMovementSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)
    product_sku = serializers.CharField(source="product.sku", read_only=True)
    movement_type_display = serializers.CharField(source="get_movement_type_display", read_only=True)
    reason_display = serializers.CharField(source="get_reason_display", read_only=True)
    created_by_name = serializers.CharField(source="created_by.display_name", read_only=True, default=None)
    signed_quantity = serializers.IntegerField(read_only=True)

    class Meta:
        model = StockMovement
        fields = (
            "id",
            "product",
            "product_name",
            "product_sku",
            "movement_type",
            "movement_type_display",
            "quantity",
            "signed_quantity",
            "reason",
            "reason_display",
            "reference",
            "notes",
            "balance_after",
            "created_by",
            "created_by_name",
            "created_at",
        )
        read_only_fields = ("id", "balance_after", "created_by", "created_at")

    def validate_quantity(self, value):
        if value < 1:
            raise serializers.ValidationError("Quantity must be at least 1.")
        return value

    def validate(self, attrs):
        reason = attrs.get("reason")
        # SALE / CHALLAN_CANCELLED rows are written by the challan workflow so
        # the ledger stays a faithful record of what actually happened.
        if reason in (MovementReason.SALE, MovementReason.CHALLAN_CANCELLED):
            raise serializers.ValidationError(
                {
                    "reason": [
                        "This reason is reserved for the sales challan workflow. "
                        "Confirm or cancel a challan instead."
                    ]
                }
            )
        return attrs


class StockAdjustSerializer(serializers.Serializer):
    """Absolute stock correction after a physical count."""

    new_quantity = serializers.IntegerField(min_value=0)
    notes = serializers.CharField(required=False, allow_blank=True, max_length=500)


class ProductImageSerializer(serializers.Serializer):
    """Multipart upload for a single product photo."""

    image = serializers.ImageField(
        help_text="JPEG, PNG or WebP, up to 5 MB. Stored on S3 when USE_S3 is enabled."
    )

    def validate_image(self, value):
        return validate_uploaded_image(value)


class InventoryStatsSerializer(serializers.Serializer):
    total_products = serializers.IntegerField()
    active_products = serializers.IntegerField()
    low_stock = serializers.IntegerField()
    out_of_stock = serializers.IntegerField()
    total_stock_units = serializers.IntegerField()
    stock_value = serializers.DecimalField(max_digits=18, decimal_places=2)
    categories = serializers.IntegerField()


CHOICES_PAYLOAD = {
    "unit": [{"value": v, "label": str(l)} for v, l in UnitOfMeasure.choices],
    "movement_type": [{"value": v, "label": str(l)} for v, l in MovementType.choices],
    "movement_reason": [
        {"value": v, "label": str(l)}
        for v, l in MovementReason.choices
        if v not in (MovementReason.SALE, MovementReason.CHALLAN_CANCELLED)
    ],
    "movement_reason_all": [{"value": v, "label": str(l)} for v, l in MovementReason.choices],
}
