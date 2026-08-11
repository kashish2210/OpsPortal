"""Challan state transitions.

    DRAFT --confirm--> CONFIRMED --cancel--> CANCELLED
      |                                          ^
      +---------------- cancel ------------------+

Confirming deducts stock; cancelling a *confirmed* challan returns it. Both run
inside a single transaction with the challan row locked, so two users clicking
"Confirm" at the same moment cannot deduct stock twice.
"""

import logging

from django.db import transaction
from django.utils import timezone

from core.exceptions import BusinessRuleError
from inventory import services as stock_services
from inventory.models import MovementReason, MovementType

from .models import ChallanStatus, SalesChallan

logger = logging.getLogger("opsportal.sales")


def _locked(challan):
    """Re-read the challan with a row lock so state checks are race-free."""
    return SalesChallan.objects.select_for_update().get(pk=challan.pk)


@transaction.atomic
def confirm_challan(challan, user=None):
    """DRAFT -> CONFIRMED, deducting stock for every line.

    Raises :class:`~core.exceptions.InsufficientStockError` (HTTP 400) listing
    every short line if the warehouse cannot cover the challan; nothing is
    written in that case.
    """
    challan = _locked(challan)

    if challan.status == ChallanStatus.CONFIRMED:
        raise BusinessRuleError(
            f"Challan {challan.challan_number} is already confirmed.",
            code="already_confirmed",
            details={"status": challan.status},
        )
    if challan.status == ChallanStatus.CANCELLED:
        raise BusinessRuleError(
            f"Challan {challan.challan_number} was cancelled and cannot be confirmed.",
            code="challan_cancelled",
            details={"status": challan.status},
        )

    items = list(challan.items.all())
    if not items:
        raise BusinessRuleError(
            "Add at least one product before confirming this challan.",
            code="empty_challan",
        )

    # Raises InsufficientStockError with a per-product breakdown when short.
    stock_services.apply_movements(
        lines=[
            stock_services.StockLine(product_id=item.product_id, quantity=item.quantity) for item in items
        ],
        movement_type=MovementType.OUT,
        reason=MovementReason.SALE,
        user=user,
        reference=challan.challan_number,
        notes=f"Sales challan {challan.challan_number} confirmed.",
        # A product archived after the draft was written should still ship.
        allow_inactive=True,
    )

    challan.status = ChallanStatus.CONFIRMED
    challan.confirmed_by = user
    challan.confirmed_at = timezone.now()
    challan.save(update_fields=["status", "confirmed_by", "confirmed_at", "updated_at"])
    challan.recalculate_totals()

    logger.info(
        "Challan %s confirmed by %s (%s lines, %s units)",
        challan.challan_number,
        getattr(user, "username", "system"),
        len(items),
        challan.total_quantity,
    )
    return challan


@transaction.atomic
def cancel_challan(challan, user=None, reason=""):
    """DRAFT or CONFIRMED -> CANCELLED.

    Cancelling a confirmed challan writes compensating IN movements so the
    warehouse balance and the ledger stay consistent.
    """
    challan = _locked(challan)

    if challan.status == ChallanStatus.CANCELLED:
        raise BusinessRuleError(
            f"Challan {challan.challan_number} is already cancelled.",
            code="already_cancelled",
            details={"status": challan.status},
        )

    was_confirmed = challan.status == ChallanStatus.CONFIRMED
    if was_confirmed:
        items = list(challan.items.all())
        if items:
            stock_services.apply_movements(
                lines=[
                    stock_services.StockLine(product_id=item.product_id, quantity=item.quantity)
                    for item in items
                ],
                movement_type=MovementType.IN,
                reason=MovementReason.CHALLAN_CANCELLED,
                user=user,
                reference=challan.challan_number,
                notes=f"Stock returned after cancelling challan {challan.challan_number}.",
                allow_inactive=True,
            )

    challan.status = ChallanStatus.CANCELLED
    challan.cancelled_by = user
    challan.cancelled_at = timezone.now()
    challan.cancellation_reason = (reason or "").strip()
    challan.save(
        update_fields=[
            "status",
            "cancelled_by",
            "cancelled_at",
            "cancellation_reason",
            "updated_at",
        ]
    )

    logger.info(
        "Challan %s cancelled by %s (stock %s)",
        challan.challan_number,
        getattr(user, "username", "system"),
        "restored" if was_confirmed else "untouched (was a draft)",
    )
    return challan


def assert_editable(challan):
    """Guard used by update/delete: confirmed documents are immutable."""
    if challan.status != ChallanStatus.DRAFT:
        raise BusinessRuleError(
            f"Challan {challan.challan_number} is {challan.get_status_display().lower()} "
            "and can no longer be edited. Cancel it and raise a new one instead.",
            code="challan_not_editable",
            details={"status": challan.status},
        )
