"""Query-string filters for the CRM endpoints."""

import django_filters as filters
from django.db.models import Q
from django.utils import timezone

from .models import Customer, CustomerStatus, FollowUp


class CustomerFilter(filters.FilterSet):
    """``/api/customers/?status=LEAD&customer_type=RETAIL&follow_up=due&q=raj``"""

    q = filters.CharFilter(method="filter_search", label="Free-text search")
    status = filters.MultipleChoiceFilter(choices=CustomerStatus.choices)
    customer_type = filters.CharFilter(field_name="customer_type", lookup_expr="iexact")
    city = filters.CharFilter(field_name="city", lookup_expr="icontains")
    has_gst = filters.BooleanFilter(method="filter_has_gst")
    follow_up = filters.ChoiceFilter(
        method="filter_follow_up",
        choices=[("due", "Due or overdue"), ("upcoming", "Upcoming"), ("none", "Not scheduled")],
    )
    created_after = filters.DateFilter(field_name="created_at", lookup_expr="date__gte")
    created_before = filters.DateFilter(field_name="created_at", lookup_expr="date__lte")

    class Meta:
        model = Customer
        fields = ["status", "customer_type", "city", "has_gst", "follow_up"]

    def filter_search(self, queryset, name, value):
        value = value.strip()
        if not value:
            return queryset
        return queryset.filter(
            Q(name__icontains=value)
            | Q(business_name__icontains=value)
            | Q(mobile__icontains=value)
            | Q(email__icontains=value)
            | Q(code__icontains=value)
            | Q(gst_number__icontains=value)
            | Q(city__icontains=value)
        )

    def filter_has_gst(self, queryset, name, value):
        return queryset.exclude(gst_number="") if value else queryset.filter(gst_number="")

    def filter_follow_up(self, queryset, name, value):
        today = timezone.localdate()
        if value == "due":
            return queryset.filter(follow_up_date__isnull=False, follow_up_date__lte=today)
        if value == "upcoming":
            return queryset.filter(follow_up_date__gt=today)
        if value == "none":
            return queryset.filter(follow_up_date__isnull=True)
        return queryset


class FollowUpFilter(filters.FilterSet):
    customer = filters.NumberFilter(field_name="customer_id")
    channel = filters.CharFilter(field_name="channel", lookup_expr="iexact")
    created_after = filters.DateFilter(field_name="created_at", lookup_expr="date__gte")
    created_before = filters.DateFilter(field_name="created_at", lookup_expr="date__lte")

    class Meta:
        model = FollowUp
        fields = ["customer", "channel"]
