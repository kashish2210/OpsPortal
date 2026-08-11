"""Product catalogue and stock ledger.

``Product.current_stock`` is a running balance kept in sync by
:mod:`inventory.services`; :class:`StockMovement` is the append-only ledger that
explains every change to it. Stock is never edited directly - it always moves
through a movement row, so the two can be reconciled at any time.
"""

import uuid

from django.core.validators import MinValueValidator
from django.db import models
from django.utils.translation import gettext_lazy as _

from core.models import AuthoredModel, TimeStampedModel


def product_image_path(instance, filename):
    """Store product photos under a stable, collision-free key.

    Using the SKU keeps objects greppable in the bucket, and the uuid means
    re-uploading never overwrites (or is cached as) the previous image.
    """
    extension = (filename.rsplit(".", 1)[-1] if "." in filename else "jpg").lower()
    sku = (instance.sku or "product").replace("/", "-")
    return f"products/{sku}/{uuid.uuid4().hex}.{extension}"


class MovementType(models.TextChoices):
    IN = "IN", _("Stock in")
    OUT = "OUT", _("Stock out")


class MovementReason(models.TextChoices):
    OPENING = "OPENING", _("Opening balance")
    PURCHASE = "PURCHASE", _("Purchase received")
    SALE = "SALE", _("Sales challan")
    SALES_RETURN = "SALES_RETURN", _("Sales return")
    PURCHASE_RETURN = "PURCHASE_RETURN", _("Purchase return")
    CHALLAN_CANCELLED = "CHALLAN_CANCELLED", _("Challan cancelled")
    DAMAGE = "DAMAGE", _("Damaged / expired")
    ADJUSTMENT = "ADJUSTMENT", _("Manual adjustment")
    TRANSFER = "TRANSFER", _("Warehouse transfer")


class UnitOfMeasure(models.TextChoices):
    PCS = "PCS", _("Pieces")
    BOX = "BOX", _("Box")
    KG = "KG", _("Kilogram")
    LTR = "LTR", _("Litre")
    MTR = "MTR", _("Metre")
    PKT = "PKT", _("Packet")
    SET = "SET", _("Set")


class ProductQuerySet(models.QuerySet):
    def active(self):
        return self.filter(is_active=True)

    def low_stock(self):
        """At or below the alert level (including out of stock)."""
        return self.filter(is_active=True, current_stock__lte=models.F("min_stock_alert"))

    def out_of_stock(self):
        return self.filter(is_active=True, current_stock__lte=0)


class Product(AuthoredModel):
    name = models.CharField(_("product name"), max_length=180, db_index=True)
    sku = models.CharField(
        _("SKU / code"),
        max_length=50,
        unique=True,
        db_index=True,
        error_messages={"unique": _("This SKU is already used by another product.")},
    )
    category = models.CharField(_("category"), max_length=80, db_index=True)
    description = models.TextField(_("description"), blank=True)

    unit = models.CharField(
        _("unit"), max_length=10, choices=UnitOfMeasure.choices, default=UnitOfMeasure.PCS
    )
    unit_price = models.DecimalField(
        _("unit price"), max_digits=12, decimal_places=2, validators=[MinValueValidator(0)]
    )
    hsn_code = models.CharField(_("HSN code"), max_length=15, blank=True)
    tax_rate = models.DecimalField(
        _("GST %"), max_digits=5, decimal_places=2, default=0, validators=[MinValueValidator(0)]
    )

    current_stock = models.IntegerField(
        _("current stock"),
        default=0,
        editable=False,
        help_text=_("Maintained by stock movements - never edited directly."),
    )
    min_stock_alert = models.PositiveIntegerField(
        _("minimum stock alert"),
        default=0,
        help_text=_("A low-stock warning is raised at or below this quantity."),
    )
    location = models.CharField(
        _("location / warehouse"), max_length=120, blank=True, db_index=True
    )
    is_active = models.BooleanField(_("active"), default=True, db_index=True)

    # Written through Django's storage API, so it lands on the local volume or
    # in S3 depending on USE_S3 - no code change either way.
    image = models.ImageField(
        _("product image"),
        upload_to=product_image_path,
        blank=True,
        null=True,
        help_text=_("Optional photo. Stored on S3 when USE_S3 is enabled."),
    )

    objects = ProductQuerySet.as_manager()

    class Meta:
        ordering = ("name",)
        verbose_name = _("product")
        verbose_name_plural = _("products")
        indexes = [
            models.Index(fields=["category", "is_active"]),
            models.Index(fields=["location"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(current_stock__gte=0),
                name="inventory_product_stock_not_negative",
            ),
            models.CheckConstraint(
                condition=models.Q(unit_price__gte=0),
                name="inventory_product_price_not_negative",
            ),
        ]

    def __str__(self):
        return f"{self.sku} - {self.name}"

    def save(self, *args, **kwargs):
        if self.sku:
            self.sku = self.sku.upper().strip()
        if self.category:
            self.category = self.category.strip()
        super().save(*args, **kwargs)

    @property
    def is_low_stock(self):
        return self.is_active and self.current_stock <= self.min_stock_alert

    @property
    def is_out_of_stock(self):
        return self.current_stock <= 0

    @property
    def stock_value(self):
        return self.current_stock * self.unit_price

    def snapshot(self):
        """The product data copied onto a challan line at save time."""
        return {
            "product_name": self.name,
            "product_sku": self.sku,
            "product_category": self.category,
            "product_unit": self.unit,
            "product_location": self.location,
            "unit_price": self.unit_price,
            "tax_rate": self.tax_rate,
        }


class StockMovement(TimeStampedModel):
    """Append-only ledger row: one recorded change to a product's stock."""

    product = models.ForeignKey(
        Product, on_delete=models.PROTECT, related_name="movements", verbose_name=_("product")
    )
    movement_type = models.CharField(
        _("movement type"), max_length=3, choices=MovementType.choices, db_index=True
    )
    quantity = models.PositiveIntegerField(
        _("quantity changed"), validators=[MinValueValidator(1)]
    )
    reason = models.CharField(
        _("reason"), max_length=30, choices=MovementReason.choices, default=MovementReason.ADJUSTMENT
    )
    reference = models.CharField(
        _("reference"), max_length=60, blank=True, db_index=True,
        help_text=_("Challan number, purchase invoice number, ..."),
    )
    notes = models.TextField(_("notes"), blank=True)

    balance_after = models.IntegerField(
        _("balance after"), help_text=_("Stock on hand immediately after this movement.")
    )
    created_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="stock_movements",
        verbose_name=_("created by"),
    )

    class Meta:
        ordering = ("-created_at", "-id")
        verbose_name = _("stock movement")
        verbose_name_plural = _("stock movements")
        indexes = [
            models.Index(fields=["product", "-created_at"]),
            models.Index(fields=["movement_type", "reason"]),
        ]

    def __str__(self):
        sign = "+" if self.movement_type == MovementType.IN else "-"
        return f"{self.product.sku} {sign}{self.quantity} ({self.get_reason_display()})"

    @property
    def signed_quantity(self):
        return self.quantity if self.movement_type == MovementType.IN else -self.quantity
