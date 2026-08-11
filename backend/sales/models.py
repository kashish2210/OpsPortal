"""Sales challan (delivery note) models.

Two deliberate design choices, both required by the brief:

1. **Snapshots.** A challan line copies the product's name, SKU, category, unit
   and price at the moment it is saved. Re-pricing or renaming a product later
   must never rewrite history on an already-issued document.
2. **Stock only moves on confirmation.** A DRAFT challan reserves nothing.
   Confirming it deducts stock atomically (see :mod:`sales.services`);
   cancelling a confirmed challan puts the stock back.
"""

from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from core.models import TimeStampedModel
from core.sequences import Sequence


class ChallanStatus(models.TextChoices):
    DRAFT = "DRAFT", _("Draft")
    CONFIRMED = "CONFIRMED", _("Confirmed")
    CANCELLED = "CANCELLED", _("Cancelled")


class SalesChallanQuerySet(models.QuerySet):
    def drafts(self):
        return self.filter(status=ChallanStatus.DRAFT)

    def confirmed(self):
        return self.filter(status=ChallanStatus.CONFIRMED)

    def cancelled(self):
        return self.filter(status=ChallanStatus.CANCELLED)


class SalesChallan(TimeStampedModel):
    challan_number = models.CharField(
        _("challan number"),
        max_length=30,
        unique=True,
        editable=False,
        db_index=True,
        help_text=_("Auto-generated, e.g. CH-202608-00017."),
    )
    customer = models.ForeignKey(
        "crm.Customer",
        on_delete=models.PROTECT,
        related_name="challans",
        verbose_name=_("customer"),
    )

    # -- customer snapshot (billing details as they were at issue time) -----
    customer_name = models.CharField(max_length=150, blank=True)
    customer_business_name = models.CharField(max_length=180, blank=True)
    customer_mobile = models.CharField(max_length=20, blank=True)
    customer_gst_number = models.CharField(max_length=15, blank=True)
    customer_address = models.TextField(blank=True)

    status = models.CharField(
        _("status"),
        max_length=20,
        choices=ChallanStatus.choices,
        default=ChallanStatus.DRAFT,
        db_index=True,
    )
    challan_date = models.DateField(_("challan date"), default=timezone.localdate, db_index=True)
    notes = models.TextField(_("notes"), blank=True)
    delivery_address = models.TextField(_("delivery address"), blank=True)
    vehicle_number = models.CharField(_("vehicle number"), max_length=30, blank=True)

    # -- rolled-up totals (recalculated from the lines) ---------------------
    total_quantity = models.PositiveIntegerField(_("total quantity"), default=0)
    total_amount = models.DecimalField(
        _("total amount"), max_digits=14, decimal_places=2, default=Decimal("0.00")
    )
    total_tax = models.DecimalField(
        _("total tax"), max_digits=14, decimal_places=2, default=Decimal("0.00")
    )
    grand_total = models.DecimalField(
        _("grand total"), max_digits=14, decimal_places=2, default=Decimal("0.00")
    )

    # -- audit trail --------------------------------------------------------
    created_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="challans_created",
        verbose_name=_("created by"),
    )
    confirmed_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="challans_confirmed",
    )
    confirmed_at = models.DateTimeField(null=True, blank=True)
    cancelled_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="challans_cancelled",
    )
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancellation_reason = models.TextField(blank=True)

    objects = SalesChallanQuerySet.as_manager()

    class Meta:
        ordering = ("-challan_date", "-id")
        verbose_name = _("sales challan")
        verbose_name_plural = _("sales challans")
        indexes = [
            models.Index(fields=["status", "-challan_date"]),
            models.Index(fields=["customer", "-challan_date"]),
        ]

    def __str__(self):
        return f"{self.challan_number} - {self.customer_name or self.customer_id}"

    def save(self, *args, **kwargs):
        if not self.challan_number:
            self.challan_number = self.generate_number(self.challan_date)
        if self.customer_id and not self.customer_name:
            self.copy_customer_snapshot()
        super().save(*args, **kwargs)

    # -- helpers ------------------------------------------------------------
    @staticmethod
    def generate_number(on_date=None):
        """``CH-YYYYMM-00001`` - the counter restarts every month."""
        on_date = on_date or timezone.localdate()
        period = on_date.strftime("%Y%m")
        return Sequence.next_formatted(
            f"sales.challan:{period}", prefix=f"CH-{period}-", padding=5
        )

    def copy_customer_snapshot(self):
        customer = self.customer
        self.customer_name = customer.name
        self.customer_business_name = customer.business_name
        self.customer_mobile = customer.mobile
        self.customer_gst_number = customer.gst_number
        self.customer_address = customer.full_address

    def recalculate_totals(self, save=True):
        aggregates = self.items.aggregate(
            quantity=models.Sum("quantity"),
            amount=models.Sum("line_total"),
            tax=models.Sum("line_tax"),
        )
        self.total_quantity = aggregates["quantity"] or 0
        self.total_amount = aggregates["amount"] or Decimal("0.00")
        self.total_tax = aggregates["tax"] or Decimal("0.00")
        self.grand_total = self.total_amount + self.total_tax
        if save:
            self.save(
                update_fields=[
                    "total_quantity",
                    "total_amount",
                    "total_tax",
                    "grand_total",
                    "updated_at",
                ]
            )
        return self

    @property
    def is_editable(self):
        """Only drafts can be modified - confirmed documents are immutable."""
        return self.status == ChallanStatus.DRAFT

    @property
    def can_confirm(self):
        return self.status == ChallanStatus.DRAFT and self.items.exists()

    @property
    def can_cancel(self):
        return self.status in (ChallanStatus.DRAFT, ChallanStatus.CONFIRMED)

    @property
    def line_count(self):
        return self.items.count()


class ChallanItem(models.Model):
    """A single line on a challan, carrying its own product snapshot."""

    challan = models.ForeignKey(
        SalesChallan, on_delete=models.CASCADE, related_name="items", verbose_name=_("challan")
    )
    product = models.ForeignKey(
        "inventory.Product",
        on_delete=models.PROTECT,
        related_name="challan_items",
        verbose_name=_("product"),
    )

    # -- product snapshot: frozen at save time, never refreshed -------------
    product_name = models.CharField(_("product name"), max_length=180)
    product_sku = models.CharField(_("SKU"), max_length=50)
    product_category = models.CharField(_("category"), max_length=80, blank=True)
    product_unit = models.CharField(_("unit"), max_length=10, blank=True)
    product_location = models.CharField(_("location"), max_length=120, blank=True)
    unit_price = models.DecimalField(
        _("unit price"), max_digits=12, decimal_places=2, validators=[MinValueValidator(0)]
    )
    tax_rate = models.DecimalField(_("GST %"), max_digits=5, decimal_places=2, default=0)

    quantity = models.PositiveIntegerField(_("quantity"), validators=[MinValueValidator(1)])
    line_total = models.DecimalField(
        _("line total"), max_digits=14, decimal_places=2, default=Decimal("0.00")
    )
    line_tax = models.DecimalField(
        _("line tax"), max_digits=14, decimal_places=2, default=Decimal("0.00")
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("id",)
        verbose_name = _("challan item")
        verbose_name_plural = _("challan items")
        constraints = [
            models.CheckConstraint(
                condition=models.Q(quantity__gte=1), name="sales_challanitem_quantity_positive"
            )
        ]

    def __str__(self):
        return f"{self.product_sku} x {self.quantity}"

    def take_snapshot(self, *, keep_price=False):
        """Freeze the product's current details onto this line.

        ``keep_price=True`` preserves a price the user typed on the line
        (negotiated rates) instead of overwriting it with the catalogue price.
        """
        if not self.product_id:
            return
        snapshot = self.product.snapshot()
        if keep_price:
            snapshot.pop("unit_price", None)
            snapshot.pop("tax_rate", None)
        for field, value in snapshot.items():
            setattr(self, field, value)

    def compute_totals(self):
        self.line_total = (self.unit_price or Decimal("0.00")) * self.quantity
        self.line_tax = (self.line_total * (self.tax_rate or Decimal("0.00")) / Decimal("100")).quantize(
            Decimal("0.01")
        )
        return self

    def save(self, *args, **kwargs):
        if not self.product_sku:
            self.take_snapshot(keep_price=self.unit_price is not None)
        self.compute_totals()
        super().save(*args, **kwargs)
