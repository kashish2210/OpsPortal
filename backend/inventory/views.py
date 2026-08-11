"""Product & inventory API."""

from decimal import Decimal

from django.db.models import Count, DecimalField, F, Q, Sum
from django.db.models.functions import Coalesce
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from accounts.models import Role
from core.mixins import AuditedModelMixin
from core.permissions import RolePermission

from . import services
from .filters import ProductFilter, StockMovementFilter
from .models import MovementReason, MovementType, Product, StockMovement
from .serializers import (
    CHOICES_PAYLOAD,
    InventoryStatsSerializer,
    ProductImageSerializer,
    ProductListSerializer,
    ProductOptionSerializer,
    ProductSerializer,
    StockAdjustSerializer,
    StockMovementSerializer,
)


@extend_schema_view(
    list=extend_schema(
        tags=["Products"],
        summary="List products",
        parameters=[
            OpenApiParameter("q", str, description="Search name, SKU, category, HSN or location."),
            OpenApiParameter("category", str),
            OpenApiParameter("location", str),
            OpenApiParameter("stock", str, description="low | out | in"),
            OpenApiParameter("is_active", bool),
            OpenApiParameter("page", int),
            OpenApiParameter("page_size", int),
            OpenApiParameter("ordering", str, description="e.g. name, -current_stock, unit_price"),
        ],
    ),
    retrieve=extend_schema(tags=["Products"], summary="Product detail"),
    create=extend_schema(tags=["Products"], summary="Add product"),
    partial_update=extend_schema(tags=["Products"], summary="Edit product"),
    destroy=extend_schema(tags=["Products"], summary="Archive product"),
)
class ProductViewSet(AuditedModelMixin, viewsets.ModelViewSet):
    queryset = Product.objects.select_related("created_by").all()
    permission_classes = [IsAuthenticated, RolePermission]
    filterset_class = ProductFilter
    search_fields = ["name", "sku", "category", "hsn_code", "location"]
    ordering_fields = ["name", "sku", "unit_price", "current_stock", "category", "created_at"]
    ordering = ["name"]

    # Warehouse owns the catalogue; everyone else reads it.
    read_roles = {Role.ADMIN, Role.SALES, Role.WAREHOUSE, Role.ACCOUNTS}
    write_roles = {Role.ADMIN, Role.WAREHOUSE}

    def get_serializer_class(self):
        if self.action == "list":
            return ProductListSerializer
        if self.action == "options":
            return ProductOptionSerializer
        return ProductSerializer

    def perform_create(self, serializer):
        opening_stock = serializer.validated_data.pop("opening_stock", 0)
        product = serializer.save(created_by=self.request.user, updated_by=self.request.user)
        if opening_stock:
            services.apply_movement(
                product=product,
                quantity=opening_stock,
                movement_type=MovementType.IN,
                reason=MovementReason.OPENING,
                user=self.request.user,
                notes="Opening balance recorded when the product was created.",
            )
            product.refresh_from_db(fields=["current_stock"])

    def perform_update(self, serializer):
        serializer.validated_data.pop("opening_stock", None)
        serializer.save(updated_by=self.request.user)

    def perform_destroy(self, instance):
        # Products are referenced by stock movements and challan lines.
        instance.is_active = False
        instance.save(update_fields=["is_active", "updated_at"])

    @extend_schema(
        tags=["Products"],
        summary="Product picker options",
        description="Slim, unpaginated list (max 50) for the challan builder.",
        responses={200: ProductOptionSerializer(many=True)},
    )
    @action(detail=False, methods=["get"])
    def options(self, request):
        term = request.query_params.get("q", "").strip()
        qs = Product.objects.active()
        if term:
            qs = qs.filter(Q(name__icontains=term) | Q(sku__icontains=term) | Q(category__icontains=term))
        if request.query_params.get("in_stock") == "true":
            qs = qs.filter(current_stock__gt=0)
        serializer = ProductOptionSerializer(qs.order_by("name")[:50], many=True)
        return Response(serializer.data)

    @extend_schema(
        tags=["Products"],
        summary="Stock movement history for one product",
        responses={200: StockMovementSerializer(many=True)},
    )
    @action(detail=True, methods=["get"], url_path="movements")
    def movements(self, request, pk=None):
        product = self.get_object()
        queryset = product.movements.select_related("created_by").all()
        page = self.paginate_queryset(queryset)
        serializer = StockMovementSerializer(page if page is not None else queryset, many=True)
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)

    @extend_schema(
        tags=["Products"],
        summary="Correct stock to an absolute figure",
        description="Records the difference as an ADJUSTMENT movement (stock-take).",
        request=StockAdjustSerializer,
        responses={200: ProductSerializer},
    )
    @action(detail=True, methods=["post"], url_path="adjust-stock")
    def adjust_stock(self, request, pk=None):
        product = self.get_object()
        serializer = StockAdjustSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.set_stock(
            product=product,
            new_quantity=serializer.validated_data["new_quantity"],
            user=request.user,
            notes=serializer.validated_data.get("notes", ""),
        )
        product.refresh_from_db()
        return Response(ProductSerializer(product, context={"request": request}).data)

    @extend_schema(
        tags=["Products"],
        summary="Upload a product image",
        description=(
            "Multipart upload of a single product photo (JPEG/PNG/WebP, max 5 MB). "
            "Written through Django's storage API, so it lands on the local media "
            "volume by default and in the configured S3 bucket when `USE_S3=True` "
            "- no code change either way. Replacing an image deletes the old object."
        ),
        request={"multipart/form-data": ProductImageSerializer},
        responses={200: ProductSerializer},
    )
    @action(
        detail=True,
        methods=["post", "delete"],
        url_path="image",
        parser_classes=[MultiPartParser, FormParser],
    )
    def image(self, request, pk=None):
        product = self.get_object()

        if request.method == "DELETE":
            if product.image:
                product.image.delete(save=False)
                product.image = None
                product.save(update_fields=["image", "updated_at"])
            return Response(ProductSerializer(product, context={"request": request}).data)

        serializer = ProductImageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Drop the previous object so replacing a photo does not orphan files
        # in the bucket.
        if product.image:
            product.image.delete(save=False)

        product.image = serializer.validated_data["image"]
        product.updated_by = request.user
        product.save(update_fields=["image", "updated_by", "updated_at"])
        return Response(ProductSerializer(product, context={"request": request}).data)

    @extend_schema(
        tags=["Products"],
        summary="Low-stock products",
        responses={200: ProductListSerializer(many=True)},
    )
    @action(detail=False, methods=["get"], url_path="low-stock")
    def low_stock(self, request):
        queryset = Product.objects.low_stock().order_by("current_stock", "name")
        page = self.paginate_queryset(queryset)
        serializer = ProductListSerializer(page if page is not None else queryset, many=True)
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)

    @extend_schema(tags=["Products"], summary="Distinct categories")
    @action(detail=False, methods=["get"])
    def categories(self, request):
        values = (
            Product.objects.exclude(category="")
            .values("category")
            .annotate(count=Count("id"))
            .order_by("category")
        )
        return Response(list(values))

    @extend_schema(tags=["Products"], summary="Distinct locations / warehouses")
    @action(detail=False, methods=["get"])
    def locations(self, request):
        values = (
            Product.objects.exclude(location="")
            .values("location")
            .annotate(count=Count("id"))
            .order_by("location")
        )
        return Response(list(values))

    @extend_schema(tags=["Products"], summary="Inventory counters", responses={200: InventoryStatsSerializer})
    @action(detail=False, methods=["get"])
    def stats(self, request):
        base = Product.objects.all()
        aggregates = base.filter(is_active=True).aggregate(
            total_stock_units=Coalesce(Sum("current_stock"), 0),
            stock_value=Coalesce(
                Sum(
                    F("current_stock") * F("unit_price"),
                    output_field=DecimalField(max_digits=18, decimal_places=2),
                ),
                Decimal("0.00"),
                output_field=DecimalField(max_digits=18, decimal_places=2),
            ),
        )
        payload = {
            "total_products": base.count(),
            "active_products": base.filter(is_active=True).count(),
            "low_stock": base.low_stock().count(),
            "out_of_stock": base.out_of_stock().count(),
            "total_stock_units": aggregates["total_stock_units"],
            "stock_value": aggregates["stock_value"],
            "categories": base.exclude(category="").values("category").distinct().count(),
        }
        return Response(InventoryStatsSerializer(payload).data)

    @extend_schema(tags=["Products"], summary="Choice lists")
    @action(detail=False, methods=["get"])
    def choices(self, request):
        return Response(CHOICES_PAYLOAD)


@extend_schema_view(
    list=extend_schema(
        tags=["Stock"],
        summary="Stock movement log",
        parameters=[
            OpenApiParameter("product", int),
            OpenApiParameter("sku", str),
            OpenApiParameter("movement_type", str, description="IN | OUT"),
            OpenApiParameter("reason", str),
            OpenApiParameter("reference", str, description="e.g. a challan number"),
            OpenApiParameter("created_after", str, description="YYYY-MM-DD"),
            OpenApiParameter("created_before", str, description="YYYY-MM-DD"),
        ],
    ),
    create=extend_schema(
        tags=["Stock"],
        summary="Record a stock movement",
        description=(
            "Adds stock (IN) or removes it (OUT) and updates the product balance "
            "atomically. Stock can never go below zero - a short OUT movement "
            "returns HTTP 400 with an `insufficient_stock` error."
        ),
    ),
    retrieve=extend_schema(tags=["Stock"], summary="Movement detail"),
)
class StockMovementViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """The stock ledger. Append-only: rows are never edited or deleted."""

    queryset = StockMovement.objects.select_related("product", "created_by").all()
    serializer_class = StockMovementSerializer
    permission_classes = [IsAuthenticated, RolePermission]
    filterset_class = StockMovementFilter
    search_fields = ["product__name", "product__sku", "reference", "notes"]
    ordering_fields = ["created_at", "quantity"]
    ordering = ["-created_at"]

    read_roles = {Role.ADMIN, Role.SALES, Role.WAREHOUSE, Role.ACCOUNTS}
    write_roles = {Role.ADMIN, Role.WAREHOUSE}

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        movement = services.apply_movement(
            product=data["product"],
            quantity=data["quantity"],
            movement_type=data["movement_type"],
            reason=data.get("reason", MovementReason.ADJUSTMENT),
            user=request.user,
            reference=data.get("reference", ""),
            notes=data.get("notes", ""),
        )
        output = StockMovementSerializer(movement, context=self.get_serializer_context())
        return Response(output.data, status=status.HTTP_201_CREATED)
