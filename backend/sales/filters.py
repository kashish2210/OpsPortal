"""Query-string filters for the sales challan endpoints."""

import django_filters as filters
from django.db.models import Q

from .models import ChallanStatus, SalesChallan


class SalesChallanFilter(filters.FilterSet):
    """``/api/challans/?status=DRAFT&customer=12&date_from=2026-08-01&q=CH-2026``"""

    q = filters.CharFilter(method="filter_search", label="Free-text search")
    status = filters.MultipleChoiceFilter(choices=ChallanStatus.choices)
    customer = filters.NumberFilter(field_name="customer_id")
    created_by = filters.NumberFilter(field_name="created_by_id")
    date_from = filters.DateFilter(field_name="challan_date", lookup_expr="gte")
    date_to = filters.DateFilter(field_name="challan_date", lookup_expr="lte")
    min_amount = filters.NumberFilter(field_name="grand_total", lookup_expr="gte")
    max_amount = filters.NumberFilter(field_name="grand_total", lookup_expr="lte")
    product = filters.NumberFilter(
        field_name="items__product_id", distinct=True, label="Contains product id"
    )

    class Meta:
        model = SalesChallan
        fields = ["status", "customer", "created_by", "date_from", "date_to"]

    def filter_search(self, queryset, name, value):
        value = value.strip()
        if not value:
            return queryset
        return queryset.filter(
            Q(challan_number__icontains=value)
            | Q(customer_name__icontains=value)
            | Q(customer_business_name__icontains=value)
            | Q(customer_mobile__icontains=value)
            | Q(vehicle_number__icontains=value)
            | Q(items__product_sku__icontains=value)
        ).distinct()
