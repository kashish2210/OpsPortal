"""Sales challan API."""

from decimal import Decimal

from django.db import transaction
from django.db.models import Count, DecimalField, Sum
from django.db.models.functions import Coalesce
from django.http import HttpResponse
from django.utils import timezone
from drf_spectacular.utils import (
    OpenApiExample,
    OpenApiParameter,
    OpenApiResponse,
    OpenApiTypes,
    extend_schema,
    extend_schema_view,
)
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.renderers import BaseRenderer
from rest_framework.response import Response

from accounts.models import Role
from core.permissions import RolePermission
from inventory.models import StockMovement
from inventory.serializers import StockMovementSerializer

from . import services
from .filters import SalesChallanFilter
from .models import ChallanStatus, SalesChallan
from .pdf import challan_pdf_filename, render_challan_pdf
from .serializers import (
    CHOICES_PAYLOAD,
    ChallanCancelSerializer,
    SalesChallanListSerializer,
    SalesChallanSerializer,
    SalesStatsSerializer,
)


class PDFRenderer(BaseRenderer):
    """Lets a DRF action return raw PDF bytes with the right content type."""

    media_type = "application/pdf"
    format = "pdf"
    charset = None
    render_style = "binary"

    def render(self, data, accepted_media_type=None, renderer_context=None):
        return data


@extend_schema_view(
    list=extend_schema(
        tags=["Challans"],
        summary="List sales challans",
        parameters=[
            OpenApiParameter("q", str, description="Search challan no., customer, vehicle or SKU."),
            OpenApiParameter("status", str, description="DRAFT | CONFIRMED | CANCELLED (repeatable)."),
            OpenApiParameter("customer", int),
            OpenApiParameter("date_from", str, description="YYYY-MM-DD"),
            OpenApiParameter("date_to", str, description="YYYY-MM-DD"),
            OpenApiParameter("page", int),
            OpenApiParameter("page_size", int),
            OpenApiParameter("ordering", str, description="e.g. -challan_date, grand_total"),
        ],
    ),
    retrieve=extend_schema(tags=["Challans"], summary="Challan detail (with lines)"),
    create=extend_schema(
        tags=["Challans"],
        summary="Create a challan",
        description=(
            "Creates the challan and its lines. Pass `confirm: true` to confirm "
            "it in the same request, which deducts stock atomically. If any line "
            "exceeds available stock the whole request fails with HTTP 400 and an "
            "`insufficient_stock` error listing every short product."
        ),
        examples=[
            OpenApiExample(
                "Draft challan",
                value={
                    "customer": 1,
                    "challan_date": "2026-08-10",
                    "notes": "Deliver before 6 pm",
                    "confirm": False,
                    "items": [
                        {"product": 3, "quantity": 10},
                        {"product": 7, "quantity": 2, "unit_price": "450.00"},
                    ],
                },
                request_only=True,
            )
        ],
    ),
    partial_update=extend_schema(
        tags=["Challans"],
        summary="Edit a draft challan",
        description="Only DRAFT challans can be edited. Sending `items` replaces all lines.",
    ),
    destroy=extend_schema(
        tags=["Challans"],
        summary="Delete a draft challan",
        description="Only DRAFT challans can be deleted; confirmed ones must be cancelled.",
    ),
)
class SalesChallanViewSet(viewsets.ModelViewSet):
    """Raise, confirm and cancel delivery challans."""

    queryset = (
        SalesChallan.objects.select_related("customer", "created_by", "confirmed_by", "cancelled_by")
        .prefetch_related("items")
        .annotate(item_count=Count("items", distinct=True))
    )
    permission_classes = [IsAuthenticated, RolePermission]
    filterset_class = SalesChallanFilter
    search_fields = ["challan_number", "customer_name", "customer_mobile", "vehicle_number"]
    ordering_fields = ["challan_date", "created_at", "grand_total", "total_quantity", "challan_number"]
    ordering = ["-challan_date", "-id"]

    # Sales raises challans; warehouse and accounts read them.
    read_roles = {Role.ADMIN, Role.SALES, Role.WAREHOUSE, Role.ACCOUNTS}
    write_roles = {Role.ADMIN, Role.SALES}

    def get_serializer_class(self):
        if self.action == "list":
            return SalesChallanListSerializer
        return SalesChallanSerializer

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        should_confirm = serializer.validated_data.get("confirm", False)
        challan = serializer.save(created_by=request.user)

        if should_confirm:
            # Save-and-confirm is all or nothing: an InsufficientStockError
            # here rolls back the challan too, so a 400 never leaves a
            # half-created document behind.
            challan = services.confirm_challan(challan, user=request.user)

        output = SalesChallanSerializer(
            self.get_queryset().get(pk=challan.pk), context=self.get_serializer_context()
        )
        return Response(output.data, status=status.HTTP_201_CREATED)

    def perform_destroy(self, instance):
        services.assert_editable(instance)
        instance.delete()

    @extend_schema(
        tags=["Challans"],
        summary="Confirm a challan (deducts stock)",
        request=None,
        responses={200: SalesChallanSerializer},
        description=(
            "DRAFT -> CONFIRMED. Locks every referenced product, verifies stock, "
            "writes OUT movements and reduces the balances - all in one "
            "transaction. Returns 400 `insufficient_stock` (with a `shortages` "
            "list) if the warehouse cannot cover the challan."
        ),
    )
    @action(detail=True, methods=["post"])
    def confirm(self, request, pk=None):
        challan = self.get_object()
        challan = services.confirm_challan(challan, user=request.user)
        return Response(
            SalesChallanSerializer(
                self.get_queryset().get(pk=challan.pk), context=self.get_serializer_context()
            ).data
        )

    @extend_schema(
        tags=["Challans"],
        summary="Cancel a challan",
        request=ChallanCancelSerializer,
        responses={200: SalesChallanSerializer},
        description=(
            "DRAFT or CONFIRMED -> CANCELLED. Cancelling a confirmed challan "
            "writes compensating IN movements so the stock is returned."
        ),
    )
    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        challan = self.get_object()
        serializer = ChallanCancelSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        challan = services.cancel_challan(
            challan, user=request.user, reason=serializer.validated_data.get("reason", "")
        )
        return Response(
            SalesChallanSerializer(
                self.get_queryset().get(pk=challan.pk), context=self.get_serializer_context()
            ).data
        )

    @extend_schema(
        tags=["Challans"],
        summary="Stock movements generated by this challan",
        responses={200: StockMovementSerializer(many=True)},
    )
    @action(detail=True, methods=["get"], url_path="stock-movements")
    def stock_movements(self, request, pk=None):
        challan = self.get_object()
        movements = (
            StockMovement.objects.filter(reference=challan.challan_number)
            .select_related("product", "created_by")
            .order_by("-created_at")
        )
        return Response(StockMovementSerializer(movements, many=True).data)

    @extend_schema(
        tags=["Challans"],
        summary="Download the challan as a PDF",
        description=(
            "Renders the challan as an A4 delivery-challan PDF using the stored "
            "snapshot columns, so a re-print reproduces the document exactly as "
            "it was issued. Drafts and cancelled challans are watermarked.\n\n"
            "Add `?disposition=inline` to preview it in the browser instead of "
            "downloading."
        ),
        parameters=[OpenApiParameter("disposition", str, description="attachment (default) | inline")],
        responses={
            (200, "application/pdf"): OpenApiTypes.BINARY,
            404: OpenApiResponse(description="Challan not found"),
        },
    )
    @action(detail=True, methods=["get"], renderer_classes=[PDFRenderer])
    def pdf(self, request, pk=None):
        challan = self.get_object()
        pdf_bytes = render_challan_pdf(challan)

        disposition = "inline" if request.query_params.get("disposition") == "inline" else "attachment"
        response = HttpResponse(pdf_bytes, content_type="application/pdf")
        response["Content-Disposition"] = f'{disposition}; filename="{challan_pdf_filename(challan)}"'
        response["Content-Length"] = str(len(pdf_bytes))
        return response

    @extend_schema(tags=["Challans"], summary="Sales counters", responses={200: SalesStatsSerializer})
    @action(detail=False, methods=["get"])
    def stats(self, request):
        base = SalesChallan.objects.all()
        confirmed = base.filter(status=ChallanStatus.CONFIRMED)
        month_start = timezone.localdate().replace(day=1)
        money = DecimalField(max_digits=18, decimal_places=2)

        payload = {
            "total": base.count(),
            "draft": base.filter(status=ChallanStatus.DRAFT).count(),
            "confirmed": confirmed.count(),
            "cancelled": base.filter(status=ChallanStatus.CANCELLED).count(),
            "units_shipped": confirmed.aggregate(t=Coalesce(Sum("total_quantity"), 0))["t"],
            "confirmed_value": confirmed.aggregate(
                t=Coalesce(Sum("grand_total"), Decimal("0.00"), output_field=money)
            )["t"],
            "this_month_value": confirmed.filter(challan_date__gte=month_start).aggregate(
                t=Coalesce(Sum("grand_total"), Decimal("0.00"), output_field=money)
            )["t"],
        }
        return Response(SalesStatsSerializer(payload).data)

    @extend_schema(tags=["Challans"], summary="Choice lists")
    @action(detail=False, methods=["get"])
    def choices(self, request):
        return Response(CHOICES_PAYLOAD)
