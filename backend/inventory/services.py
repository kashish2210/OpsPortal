"""Stock engine.

Every change to ``Product.current_stock`` goes through this module so that:

* the product row is locked (``SELECT ... FOR UPDATE``) before it is read, which
  makes concurrent challan confirmations safe;
* stock can never be pushed below zero - the attempt raises
  :class:`core.exceptions.InsufficientStockError` carrying a per-product
  breakdown that the API returns verbatim;
* a :class:`~inventory.models.StockMovement` row is always written, recording
  who changed what, by how much, why, and the resulting balance.
"""

from dataclasses import dataclass

from django.db import transaction

from core.exceptions import BusinessRuleError, InsufficientStockError

from .models import MovementReason, MovementType, Product, StockMovement


@dataclass(frozen=True)
class StockLine:
    """One product/quantity pair in a bulk stock operation."""

    product_id: int
    quantity: int


def _lock_products(product_ids):
    """Lock the given products in a deterministic order to avoid deadlocks."""
    products = {
        product.pk: product
        for product in Product.objects.select_for_update().filter(
            pk__in=sorted(set(product_ids))
        ).order_by("pk")
    }
    missing = sorted(set(product_ids) - set(products))
    if missing:
        raise BusinessRuleError(
            "One or more products no longer exist.",
            details={"product_ids": missing},
            code="product_not_found",
        )
    return products


@transaction.atomic
def apply_movement(
    *,
    product,
    quantity,
    movement_type,
    reason=MovementReason.ADJUSTMENT,
    user=None,
    reference="",
    notes="",
):
    """Record a single stock movement and update the running balance."""
    movements = apply_movements(
        lines=[StockLine(product_id=product.pk if hasattr(product, "pk") else int(product), quantity=quantity)],
        movement_type=movement_type,
        reason=reason,
        user=user,
        reference=reference,
        notes=notes,
    )
    return movements[0]


@transaction.atomic
def apply_movements(
    *,
    lines,
    movement_type,
    reason=MovementReason.ADJUSTMENT,
    user=None,
    reference="",
    notes="",
    allow_inactive=False,
):
    """Apply several stock movements as one all-or-nothing operation.

    Raises :class:`InsufficientStockError` listing *every* short line rather
    than failing on the first one, so the UI can highlight all of them at once.
    """
    if not lines:
        return []

    # Merge duplicate products so a challan listing the same SKU twice is
    # validated against the combined quantity.
    required = {}
    for line in lines:
        if line.quantity <= 0:
            raise BusinessRuleError(
                "Quantity must be at least 1.",
                details={"product_id": line.product_id, "quantity": line.quantity},
                code="invalid_quantity",
            )
        required[line.product_id] = required.get(line.product_id, 0) + line.quantity

    products = _lock_products(required)

    if not allow_inactive:
        inactive = [p.sku for p in products.values() if not p.is_active]
        if inactive:
            raise BusinessRuleError(
                f"These products are archived and cannot be moved: {', '.join(inactive)}.",
                details={"inactive_skus": inactive},
                code="product_inactive",
            )

    if movement_type == MovementType.OUT:
        shortages = []
        for product_id, quantity in required.items():
            product = products[product_id]
            if product.current_stock < quantity:
                shortages.append(
                    {
                        "product_id": product.pk,
                        "sku": product.sku,
                        "product_name": product.name,
                        "requested": quantity,
                        "available": product.current_stock,
                        "short_by": quantity - product.current_stock,
                    }
                )
        if shortages:
            names = ", ".join(f"{s['sku']} (need {s['requested']}, have {s['available']})" for s in shortages)
            raise InsufficientStockError(
                f"Insufficient stock for: {names}.",
                details={"shortages": shortages},
            )

    movements = []
    for product_id, quantity in required.items():
        product = products[product_id]
        delta = quantity if movement_type == MovementType.IN else -quantity
        product.current_stock += delta
        product.save(update_fields=["current_stock", "updated_at"])
        movements.append(
            StockMovement(
                product=product,
                movement_type=movement_type,
                quantity=quantity,
                reason=reason,
                reference=reference,
                notes=notes,
                balance_after=product.current_stock,
                created_by=user,
            )
        )

    StockMovement.objects.bulk_create(movements)
    return movements


@transaction.atomic
def set_stock(*, product, new_quantity, user=None, notes="", reason=MovementReason.ADJUSTMENT):
    """Correct a product's stock to an absolute figure (stock-take)."""
    if new_quantity < 0:
        raise BusinessRuleError("Stock cannot be set to a negative value.", code="invalid_quantity")

    locked = Product.objects.select_for_update().get(pk=product.pk)
    delta = new_quantity - locked.current_stock
    if delta == 0:
        return None
    return apply_movement(
        product=locked,
        quantity=abs(delta),
        movement_type=MovementType.IN if delta > 0 else MovementType.OUT,
        reason=reason,
        user=user,
        notes=notes or f"Stock-take correction to {new_quantity}.",
    )


def recalculate_stock(product):
    """Rebuild ``current_stock`` from the ledger (reconciliation helper)."""
    total = 0
    for movement in product.movements.order_by("created_at", "id"):
        total += movement.signed_quantity
    Product.objects.filter(pk=product.pk).update(current_stock=total)
    return total
