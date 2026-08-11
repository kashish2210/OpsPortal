"""Customer CRM API."""

from django.db.models import Count, Q
from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from accounts.models import Role
from core.mixins import AuditedModelMixin
from core.permissions import RolePermission

from .filters import CustomerFilter, FollowUpFilter
from .models import Customer, CustomerStatus, CustomerType, FollowUp
from .serializers import (
    CHOICES_PAYLOAD,
    CustomerListSerializer,
    CustomerOptionSerializer,
    CustomerSerializer,
    CustomerStatsSerializer,
    FollowUpSerializer,
)


@extend_schema_view(
    list=extend_schema(
        tags=["Customers"],
        summary="List customers",
        parameters=[
            OpenApiParameter(
                "q", str, description="Search name, business, mobile, e-mail, code, GST or city."
            ),
            OpenApiParameter("status", str, description="LEAD | ACTIVE | INACTIVE (repeatable)."),
            OpenApiParameter("customer_type", str, description="RETAIL | WHOLESALE | DISTRIBUTOR."),
            OpenApiParameter("follow_up", str, description="due | upcoming | none."),
            OpenApiParameter("page", int),
            OpenApiParameter("page_size", int, description="Max 200."),
            OpenApiParameter("ordering", str, description="e.g. -created_at, name, follow_up_date."),
        ],
    ),
    retrieve=extend_schema(tags=["Customers"], summary="Customer detail"),
    create=extend_schema(tags=["Customers"], summary="Add customer"),
    update=extend_schema(tags=["Customers"], summary="Replace customer"),
    partial_update=extend_schema(tags=["Customers"], summary="Edit customer"),
    destroy=extend_schema(tags=["Customers"], summary="Deactivate customer"),
)
class CustomerViewSet(AuditedModelMixin, viewsets.ModelViewSet):
    """Add / edit / search customers and record follow-up notes."""

    queryset = Customer.objects.select_related("created_by").all()
    permission_classes = [IsAuthenticated, RolePermission]
    filterset_class = CustomerFilter
    search_fields = ["name", "business_name", "mobile", "email", "code", "gst_number"]
    ordering_fields = ["created_at", "name", "follow_up_date", "code", "status"]
    ordering = ["-created_at"]

    # Everyone can read the customer book; Sales and Admin maintain it.
    read_roles = {Role.ADMIN, Role.SALES, Role.WAREHOUSE, Role.ACCOUNTS}
    write_roles = {Role.ADMIN, Role.SALES}

    def get_serializer_class(self):
        if self.action == "list":
            return CustomerListSerializer
        if self.action == "options":
            return CustomerOptionSerializer
        return CustomerSerializer

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["include_follow_ups"] = self.action == "retrieve"
        return context

    def get_queryset(self):
        qs = super().get_queryset()
        if self.action == "retrieve":
            qs = qs.prefetch_related("follow_ups__created_by").annotate(
                follow_up_count=Count("follow_ups", distinct=True),
                challan_count=Count("challans", distinct=True),
            )
        return qs

    def perform_destroy(self, instance):
        # Customers are referenced by challans - archive instead of deleting.
        instance.status = CustomerStatus.INACTIVE
        instance.save(update_fields=["status", "updated_at"])

    @extend_schema(
        tags=["Customers"],
        summary="Add a follow-up note",
        request=FollowUpSerializer,
        responses={201: FollowUpSerializer},
    )
    @action(detail=True, methods=["post"], url_path="follow-ups")
    def add_follow_up(self, request, pk=None):
        customer = self.get_object()
        data = {**request.data, "customer": customer.pk}
        serializer = FollowUpSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        serializer.save(created_by=request.user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @extend_schema(
        tags=["Customers"],
        summary="List a customer's follow-ups",
        responses={200: FollowUpSerializer(many=True)},
    )
    @add_follow_up.mapping.get
    def list_follow_ups(self, request, pk=None):
        customer = self.get_object()
        queryset = customer.follow_ups.select_related("created_by").all()
        page = self.paginate_queryset(queryset)
        serializer = FollowUpSerializer(page if page is not None else queryset, many=True)
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)

    @extend_schema(
        tags=["Customers"],
        summary="Customer picker options",
        description="Slim list (no pagination, max 50) used by the challan builder.",
        responses={200: CustomerOptionSerializer(many=True)},
    )
    @action(detail=False, methods=["get"])
    def options(self, request):
        term = request.query_params.get("q", "").strip()
        qs = Customer.objects.exclude(status=CustomerStatus.INACTIVE)
        if term:
            qs = qs.filter(
                Q(name__icontains=term)
                | Q(business_name__icontains=term)
                | Q(mobile__icontains=term)
                | Q(code__icontains=term)
            )
        serializer = CustomerOptionSerializer(qs.order_by("name")[:50], many=True)
        return Response(serializer.data)

    @extend_schema(
        tags=["Customers"],
        summary="CRM counters",
        responses={200: CustomerStatsSerializer},
    )
    @action(detail=False, methods=["get"])
    def stats(self, request):
        today = timezone.localdate()
        base = Customer.objects.all()
        by_type = {
            row["customer_type"]: row["total"]
            for row in base.values("customer_type").annotate(total=Count("id"))
        }
        payload = {
            "total": base.count(),
            "leads": base.filter(status=CustomerStatus.LEAD).count(),
            "active": base.filter(status=CustomerStatus.ACTIVE).count(),
            "inactive": base.filter(status=CustomerStatus.INACTIVE).count(),
            "follow_ups_due": base.filter(follow_up_date__isnull=False, follow_up_date__lte=today)
            .exclude(status=CustomerStatus.INACTIVE)
            .count(),
            "by_type": {t.value: by_type.get(t.value, 0) for t in CustomerType},
        }
        return Response(CustomerStatsSerializer(payload).data)

    @extend_schema(
        tags=["Customers"],
        summary="Choice lists",
        description="Dropdown values for customer type, status and follow-up channel.",
    )
    @action(detail=False, methods=["get"])
    def choices(self, request):
        return Response(CHOICES_PAYLOAD)


@extend_schema_view(
    list=extend_schema(tags=["Customers"], summary="List all follow-ups"),
    create=extend_schema(tags=["Customers"], summary="Record a follow-up"),
    retrieve=extend_schema(tags=["Customers"], summary="Follow-up detail"),
)
class FollowUpViewSet(viewsets.ModelViewSet):
    """Flat access to follow-up notes across every customer."""

    queryset = FollowUp.objects.select_related("customer", "created_by").all()
    serializer_class = FollowUpSerializer
    permission_classes = [IsAuthenticated, RolePermission]
    filterset_class = FollowUpFilter
    search_fields = ["note", "customer__name", "customer__business_name"]
    ordering_fields = ["created_at", "next_follow_up_date"]
    ordering = ["-created_at"]

    read_roles = {Role.ADMIN, Role.SALES, Role.WAREHOUSE, Role.ACCOUNTS}
    write_roles = {Role.ADMIN, Role.SALES}

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)
