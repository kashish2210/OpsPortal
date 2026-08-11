"""Customer CRM models."""

from django.core.validators import RegexValidator
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from core.models import AuthoredModel, TimeStampedModel
from core.sequences import Sequence

#: 22AAAAA0000A1Z5 - state code, PAN, entity number, 'Z', checksum.
GSTIN_VALIDATOR = RegexValidator(
    regex=r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$",
    message=_("Enter a valid 15-character GSTIN, e.g. 27AAPFU0939F1ZV."),
)

MOBILE_VALIDATOR = RegexValidator(
    regex=r"^[+]?[0-9][0-9\s\-()]{6,19}$",
    message=_("Enter a valid mobile number (7-20 digits, optional +country code)."),
)

PINCODE_VALIDATOR = RegexValidator(
    regex=r"^[0-9]{4,10}$", message=_("Enter a valid postal code.")
)


class CustomerType(models.TextChoices):
    RETAIL = "RETAIL", _("Retail")
    WHOLESALE = "WHOLESALE", _("Wholesale")
    DISTRIBUTOR = "DISTRIBUTOR", _("Distributor")


class CustomerStatus(models.TextChoices):
    LEAD = "LEAD", _("Lead")
    ACTIVE = "ACTIVE", _("Active")
    INACTIVE = "INACTIVE", _("Inactive")


class FollowUpChannel(models.TextChoices):
    CALL = "CALL", _("Phone call")
    EMAIL = "EMAIL", _("E-mail")
    WHATSAPP = "WHATSAPP", _("WhatsApp")
    VISIT = "VISIT", _("Site visit")
    MEETING = "MEETING", _("Meeting")
    OTHER = "OTHER", _("Other")


class CustomerQuerySet(models.QuerySet):
    def active(self):
        return self.filter(status=CustomerStatus.ACTIVE)

    def leads(self):
        return self.filter(status=CustomerStatus.LEAD)

    def follow_ups_due(self, on=None):
        """Customers whose follow-up date has arrived (or passed)."""
        return self.filter(
            follow_up_date__isnull=False,
            follow_up_date__lte=on or timezone.localdate(),
        ).exclude(status=CustomerStatus.INACTIVE)

    def with_last_contact(self):
        return self.annotate(last_contacted_at=models.Max("follow_ups__created_at"))


class Customer(AuthoredModel):
    """A retail buyer, wholesaler or distributor the company sells to."""

    code = models.CharField(
        _("customer code"),
        max_length=20,
        unique=True,
        editable=False,
        help_text=_("Auto-generated, e.g. CUST-00042."),
    )
    name = models.CharField(_("customer name"), max_length=150, db_index=True)
    business_name = models.CharField(_("business name"), max_length=180, blank=True, db_index=True)
    # Unique: operators look customers up by phone number, and duplicate CRM
    # records for the same number are the classic data-quality problem here.
    mobile = models.CharField(
        _("mobile number"),
        max_length=20,
        unique=True,
        validators=[MOBILE_VALIDATOR],
        error_messages={"unique": _("A customer with this mobile number already exists.")},
    )
    email = models.EmailField(_("e-mail"), blank=True)
    gst_number = models.CharField(
        _("GST number"),
        max_length=15,
        blank=True,
        validators=[GSTIN_VALIDATOR],
        help_text=_("Optional. 15-character GSTIN."),
    )
    customer_type = models.CharField(
        _("customer type"),
        max_length=20,
        choices=CustomerType.choices,
        default=CustomerType.RETAIL,
        db_index=True,
    )
    status = models.CharField(
        _("status"),
        max_length=20,
        choices=CustomerStatus.choices,
        default=CustomerStatus.LEAD,
        db_index=True,
    )

    address = models.TextField(_("address"), blank=True)
    city = models.CharField(_("city"), max_length=80, blank=True, db_index=True)
    state = models.CharField(_("state"), max_length=80, blank=True)
    pincode = models.CharField(_("pincode"), max_length=10, blank=True, validators=[PINCODE_VALIDATOR])

    credit_limit = models.DecimalField(
        _("credit limit"), max_digits=12, decimal_places=2, default=0,
        help_text=_("Informational only; not enforced on challans."),
    )
    follow_up_date = models.DateField(
        _("next follow-up"), null=True, blank=True, db_index=True,
        help_text=_("Set automatically when a follow-up schedules the next contact."),
    )
    notes = models.TextField(_("notes"), blank=True)

    objects = CustomerQuerySet.as_manager()

    class Meta:
        ordering = ("-created_at",)
        verbose_name = _("customer")
        verbose_name_plural = _("customers")
        indexes = [
            models.Index(fields=["status", "customer_type"]),
            models.Index(fields=["follow_up_date"]),
        ]

    def __str__(self):
        return f"{self.code} - {self.name}"

    def save(self, *args, **kwargs):
        if self.gst_number:
            self.gst_number = self.gst_number.upper().strip()
        if self.email:
            self.email = self.email.lower().strip()
        if not self.code:
            self.code = self._generate_code()
        super().save(*args, **kwargs)

    @staticmethod
    def _generate_code():
        return Sequence.next_formatted("crm.customer", prefix="CUST-", padding=5)

    @property
    def display_name(self):
        return f"{self.name} ({self.business_name})" if self.business_name else self.name

    @property
    def is_follow_up_due(self):
        return bool(self.follow_up_date and self.follow_up_date <= timezone.localdate())

    @property
    def full_address(self):
        parts = [self.address, self.city, self.state, self.pincode]
        return ", ".join(p.strip() for p in parts if p and p.strip())


class FollowUp(TimeStampedModel):
    """A dated CRM note recorded against a customer."""

    customer = models.ForeignKey(
        Customer, on_delete=models.CASCADE, related_name="follow_ups", verbose_name=_("customer")
    )
    note = models.TextField(_("note"))
    channel = models.CharField(
        _("channel"), max_length=20, choices=FollowUpChannel.choices, default=FollowUpChannel.CALL
    )
    next_follow_up_date = models.DateField(
        _("next follow-up"), null=True, blank=True,
        help_text=_("When set, this becomes the customer's next follow-up date."),
    )
    created_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="follow_ups",
        verbose_name=_("recorded by"),
    )

    class Meta:
        ordering = ("-created_at",)
        verbose_name = _("follow-up")
        verbose_name_plural = _("follow-ups")

    def __str__(self):
        return f"{self.customer.name} - {self.get_channel_display()} on {self.created_at:%d %b %Y}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Keep the denormalised "next follow-up" on the customer in sync so the
        # dashboard can query it without a join.
        if self.next_follow_up_date and self.customer.follow_up_date != self.next_follow_up_date:
            Customer.objects.filter(pk=self.customer_id).update(
                follow_up_date=self.next_follow_up_date, updated_at=timezone.now()
            )
