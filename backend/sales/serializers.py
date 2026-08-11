"""Serializers for the sales challan module."""

from decimal import Decimal

from django.db import transaction
from rest_framework import serializers

from crm.models import CustomerStatus
from inventory.models import Product

from .models import ChallanItem, ChallanStatus, SalesChallan


class ChallanItemSerializer(serializers.ModelSerializer):
    """A challan line.

    ``product`` is the only required input; everything prefixed ``product_`` is
    a snapshot written by the server and returned read-only.
    """

    product_stock = serializers.IntegerField(source="product.current_stock", read_only=True)

    class Meta:
        model = ChallanItem
        fields = (
            "id",
            "product",
            "product_name",
            "product_sku",
            "product_category",
            "product_unit",
            "product_location",
            "product_stock",
            "unit_price",
            "tax_rate",
            "quantity",
            "line_total",
            "line_tax",
        )
        read_only_fields = (
            "id",
            "product_name",
            "product_sku",
            "product_category",
            "product_unit",
            "product_location",
            "line_total",
            "line_tax",
        )
        extra_kwargs = {
            # Omit to use the catalogue price; supply to override it.
            "unit_price": {"required": False},
            "tax_rate": {"required": False},
        }

    def validate_quantity(self, value):
        if value < 1:
            raise serializers.ValidationError("Quantity must be at least 1.")
        if value > 1_000_000:
            raise serializers.ValidationError("Quantity looks unrealistic (max 1,000,000).")
        return value

    def validate_unit_price(self, value):
        if value is not None and value < 0:
            raise serializers.ValidationError("Unit price cannot be negative.")
        return value


class SalesChallanListSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    created_by_name = serializers.CharField(source="created_by.display_name", read_only=True, default=None)
    item_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = SalesChallan
        fields = (
            "id",
            "challan_number",
            "challan_date",
            "customer",
            "customer_name",
            "customer_business_name",
            "customer_mobile",
            "status",
            "status_display",
            "total_quantity",
            "total_amount",
            "grand_total",
            "item_count",
            "created_by",
            "created_by_name",
            "created_at",
        )


class SalesChallanSerializer(serializers.ModelSerializer):
    """Create / read / update a challan together with its lines."""

    items = ChallanItemSerializer(many=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    created_by_name = serializers.CharField(source="created_by.display_name", read_only=True, default=None)
    confirmed_by_name = serializers.CharField(source="confirmed_by.display_name", read_only=True, default=None)
    cancelled_by_name = serializers.CharField(source="cancelled_by.display_name", read_only=True, default=None)
    is_editable = serializers.BooleanField(read_only=True)
    can_confirm = serializers.BooleanField(read_only=True)
    can_cancel = serializers.BooleanField(read_only=True)

    #: Accepted on create only - "Save as Draft" vs "Save & Confirm".
    confirm = serializers.BooleanField(
        write_only=True,
        required=False,
        default=False,
        help_text="Confirm immediately after saving (deducts stock).",
    )

    class Meta:
        model = SalesChallan
        fields = (
            "id",
            "challan_number",
            "challan_date",
            "customer",
            "customer_name",
            "customer_business_name",
            "customer_mobile",
            "customer_gst_number",
            "customer_address",
            "status",
            "status_display",
            "notes",
            "delivery_address",
            "vehicle_number",
            "items",
            "total_quantity",
            "total_amount",
            "total_tax",
            "grand_total",
            "is_editable",
            "can_confirm",
            "can_cancel",
            "confirm",
            "created_by",
            "created_by_name",
            "confirmed_by",
            "confirmed_by_name",
            "confirmed_at",
            "cancelled_by",
            "cancelled_by_name",
            "cancelled_at",
            "cancellation_reason",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "challan_number",
            "status",
            "customer_name",
            "customer_business_name",
            "customer_mobile",
            "customer_gst_number",
            "customer_address",
            "total_quantity",
            "total_amount",
            "total_tax",
            "grand_total",
            "created_by",
            "confirmed_by",
            "confirmed_at",
            "cancelled_by",
            "cancelled_at",
            "cancellation_reason",
            "created_at",
            "updated_at",
        )

    # -- validation --------------------------------------------------------
    def validate_customer(self, customer):
        if customer.status == CustomerStatus.INACTIVE:
            raise serializers.ValidationError(
                f"{customer.name} is marked inactive. Reactivate the customer first."
            )
        return customer

    def validate_items(self, items):
        if not items:
            raise serializers.ValidationError("A challan needs at least one product line.")
        if len(items) > 200:
            raise serializers.ValidationError("A challan can hold at most 200 lines.")

        # Merge-check duplicates: the same SKU listed twice is almost always a
        # mistake, and it hides the true quantity from the stock check.
        seen = {}
        for index, item in enumerate(items):
            product = item["product"]
            if product.pk in seen:
                raise serializers.ValidationError(
                    f"Line {index + 1}: {product.sku} is already on this challan "
                    f"(line {seen[product.pk] + 1}). Combine the quantities instead."
                )
            seen[product.pk] = index
        return items

    def validate(self, attrs):
        if self.instance and not self.instance.is_editable:
            raise serializers.ValidationError(
                f"This challan is {self.instance.get_status_display().lower()} and can no longer be edited."
            )
        return attrs

    # -- persistence -------------------------------------------------------
    def _build_items(self, challan, items_data):
        for item_data in items_data:
            product: Product = item_data["product"]
            item = ChallanItem(
                challan=challan,
                product=product,
                quantity=item_data["quantity"],
                unit_price=item_data.get("unit_price"),
                tax_rate=item_data.get("tax_rate"),
            )
            # Freeze the catalogue values unless the caller overrode them.
            item.take_snapshot(keep_price=item_data.get("unit_price") is not None)
            if item_data.get("tax_rate") is not None:
                item.tax_rate = item_data["tax_rate"]
            if item.unit_price is None:
                item.unit_price = product.unit_price
            if item.tax_rate is None:
                item.tax_rate = product.tax_rate or Decimal("0.00")
            item.save()

    @transaction.atomic
    def create(self, validated_data):
        items_data = validated_data.pop("items")
        validated_data.pop("confirm", None)  # handled by the viewset
        challan = SalesChallan(**validated_data)
        challan.copy_customer_snapshot()
        challan.save()
        self._build_items(challan, items_data)
        challan.recalculate_totals()
        return challan

    @transaction.atomic
    def update(self, instance, validated_data):
        items_data = validated_data.pop("items", None)
        validated_data.pop("confirm", None)

        for field, value in validated_data.items():
            setattr(instance, field, value)
        if "customer" in validated_data:
            instance.copy_customer_snapshot()
        instance.save()

        if items_data is not None:
            # Drafts are cheap to rewrite wholesale, and no stock has moved yet.
            instance.items.all().delete()
            self._build_items(instance, items_data)

        instance.recalculate_totals()
        return instance


class ChallanCancelSerializer(serializers.Serializer):
    reason = serializers.CharField(
        required=False, allow_blank=True, max_length=500, help_text="Why the challan is being cancelled."
    )


class SalesStatsSerializer(serializers.Serializer):
    total = serializers.IntegerField()
    draft = serializers.IntegerField()
    confirmed = serializers.IntegerField()
    cancelled = serializers.IntegerField()
    units_shipped = serializers.IntegerField()
    confirmed_value = serializers.DecimalField(max_digits=18, decimal_places=2)
    this_month_value = serializers.DecimalField(max_digits=18, decimal_places=2)


CHOICES_PAYLOAD = {
    "status": [{"value": v, "label": str(l)} for v, l in ChallanStatus.choices],
}
