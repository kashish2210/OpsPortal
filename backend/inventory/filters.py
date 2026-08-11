"""Query-string filters for the inventory endpoints."""

import django_filters as filters
from django.db.models import F, Q

from .models import MovementReason, MovementType, Product, StockMovement


class ProductFilter(filters.FilterSet):
    """``/api/products/?q=cable&category=Hardware&stock=low&is_active=true``"""

    q = filters.CharFilter(method="filter_search", label="Free-text search")
    category = filters.CharFilter(field_name="category", lookup_expr="iexact")
    location = filters.CharFilter(field_name="location", lookup_expr="icontains")
    stock = filters.ChoiceFilter(
        method="filter_stock",
        choices=[
            ("low", "At or below the alert level"),
            ("out", "Out of stock"),
            ("in", "In stock"),
        ],
    )
    min_price = filters.NumberFilter(field_name="unit_price", lookup_expr="gte")
    max_price = filters.NumberFilter(field_name="unit_price", lookup_expr="lte")

    class Meta:
        model = Product
        fields = ["category", "location", "is_active", "unit", "stock"]

    def filter_search(self, queryset, name, value):
        value = value.strip()
        if not value:
            return queryset
        return queryset.filter(
            Q(name__icontains=value)
            | Q(sku__icontains=value)
            | Q(category__icontains=value)
            | Q(hsn_code__icontains=value)
            | Q(location__icontains=value)
        )

    def filter_stock(self, queryset, name, value):
        if value == "low":
            return queryset.filter(current_stock__lte=F("min_stock_alert"))
        if value == "out":
            return queryset.filter(current_stock__lte=0)
        if value == "in":
            return queryset.filter(current_stock__gt=0)
        return queryset


class StockMovementFilter(filters.FilterSet):
    product = filters.NumberFilter(field_name="product_id")
    sku = filters.CharFilter(field_name="product__sku", lookup_expr="iexact")
    movement_type = filters.ChoiceFilter(choices=MovementType.choices)
    reason = filters.ChoiceFilter(choices=MovementReason.choices)
    reference = filters.CharFilter(field_name="reference", lookup_expr="icontains")
    created_after = filters.DateFilter(field_name="created_at", lookup_expr="date__gte")
    created_before = filters.DateFilter(field_name="created_at", lookup_expr="date__lte")
    created_by = filters.NumberFilter(field_name="created_by_id")

    class Meta:
        model = StockMovement
        fields = ["product", "movement_type", "reason", "reference", "created_by"]
