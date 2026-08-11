"""Stock engine tests - the rules that must never regress."""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from core.exceptions import BusinessRuleError, InsufficientStockError

from . import services
from .models import MovementReason, MovementType, Product, StockMovement

User = get_user_model()


def make_product(sku="TEST-1", stock=0, **kwargs):
    """Create a product and load its opening stock through the stock engine."""
    # Archiving is applied *after* the opening movement, since the engine
    # refuses to move stock for an inactive product.
    is_active = kwargs.pop("is_active", True)
    product = Product.objects.create(
        name=kwargs.pop("name", f"Product {sku}"),
        sku=sku,
        category=kwargs.pop("category", "Test"),
        unit_price=kwargs.pop("unit_price", Decimal("100.00")),
        min_stock_alert=kwargs.pop("min_stock_alert", 5),
        **kwargs,
    )
    if stock:
        services.apply_movement(
            product=product,
            quantity=stock,
            movement_type=MovementType.IN,
            reason=MovementReason.OPENING,
        )
        product.refresh_from_db()
    if not is_active:
        product.is_active = False
        product.save(update_fields=["is_active"])
    return product


class StockServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("wh", "wh@example.com", "pw", role="WAREHOUSE")

    def test_stock_in_increases_balance_and_logs_movement(self):
        product = make_product(stock=0)
        movement = services.apply_movement(
            product=product,
            quantity=25,
            movement_type=MovementType.IN,
            reason=MovementReason.PURCHASE,
            user=self.user,
            reference="PO-1",
        )
        product.refresh_from_db()

        self.assertEqual(product.current_stock, 25)
        self.assertEqual(movement.balance_after, 25)
        self.assertEqual(movement.created_by, self.user)
        self.assertEqual(movement.reference, "PO-1")
        self.assertEqual(StockMovement.objects.count(), 1)

    def test_stock_out_decreases_balance(self):
        product = make_product(stock=40)
        services.apply_movement(product=product, quantity=15, movement_type=MovementType.OUT, user=self.user)
        product.refresh_from_db()
        self.assertEqual(product.current_stock, 25)

    def test_stock_cannot_go_negative(self):
        product = make_product(stock=5)
        with self.assertRaises(InsufficientStockError) as ctx:
            services.apply_movement(
                product=product, quantity=6, movement_type=MovementType.OUT, user=self.user
            )

        shortages = ctx.exception.details["shortages"]
        self.assertEqual(len(shortages), 1)
        self.assertEqual(shortages[0]["requested"], 6)
        self.assertEqual(shortages[0]["available"], 5)
        self.assertEqual(shortages[0]["short_by"], 1)

        product.refresh_from_db()
        self.assertEqual(product.current_stock, 5, "stock must be untouched after a failed OUT")
        self.assertEqual(StockMovement.objects.filter(movement_type=MovementType.OUT).count(), 0)

    def test_bulk_out_is_all_or_nothing_and_reports_every_shortage(self):
        ok = make_product(sku="OK-1", stock=100)
        short_a = make_product(sku="SHORT-A", stock=1)
        short_b = make_product(sku="SHORT-B", stock=0)

        with self.assertRaises(InsufficientStockError) as ctx:
            services.apply_movements(
                lines=[
                    services.StockLine(ok.pk, 10),
                    services.StockLine(short_a.pk, 5),
                    services.StockLine(short_b.pk, 2),
                ],
                movement_type=MovementType.OUT,
                user=self.user,
            )

        skus = {row["sku"] for row in ctx.exception.details["shortages"]}
        self.assertEqual(skus, {"SHORT-A", "SHORT-B"})

        ok.refresh_from_db()
        self.assertEqual(ok.current_stock, 100, "the healthy line must roll back too")

    def test_duplicate_lines_are_summed_before_the_stock_check(self):
        product = make_product(stock=10)
        with self.assertRaises(InsufficientStockError):
            services.apply_movements(
                lines=[services.StockLine(product.pk, 6), services.StockLine(product.pk, 6)],
                movement_type=MovementType.OUT,
                user=self.user,
            )
        product.refresh_from_db()
        self.assertEqual(product.current_stock, 10)

    def test_zero_or_negative_quantity_is_rejected(self):
        product = make_product(stock=10)
        with self.assertRaises(BusinessRuleError):
            services.apply_movement(
                product=product, quantity=0, movement_type=MovementType.IN, user=self.user
            )

    def test_archived_products_are_blocked_unless_explicitly_allowed(self):
        product = make_product(stock=10, is_active=False)
        with self.assertRaises(BusinessRuleError):
            services.apply_movement(
                product=product, quantity=1, movement_type=MovementType.OUT, user=self.user
            )
        services.apply_movements(
            lines=[services.StockLine(product.pk, 1)],
            movement_type=MovementType.OUT,
            user=self.user,
            allow_inactive=True,
        )
        product.refresh_from_db()
        self.assertEqual(product.current_stock, 9)

    def test_set_stock_records_the_difference(self):
        product = make_product(stock=30)
        services.set_stock(product=product, new_quantity=18, user=self.user)
        product.refresh_from_db()

        self.assertEqual(product.current_stock, 18)
        last = StockMovement.objects.order_by("-id").first()
        self.assertEqual(last.movement_type, MovementType.OUT)
        self.assertEqual(last.quantity, 12)

    def test_set_stock_to_the_same_value_is_a_no_op(self):
        product = make_product(stock=30)
        before = StockMovement.objects.count()
        self.assertIsNone(services.set_stock(product=product, new_quantity=30, user=self.user))
        self.assertEqual(StockMovement.objects.count(), before)

    def test_recalculate_stock_rebuilds_from_the_ledger(self):
        product = make_product(stock=50)
        services.apply_movement(product=product, quantity=20, movement_type=MovementType.OUT)
        Product.objects.filter(pk=product.pk).update(current_stock=999)  # corrupt it

        self.assertEqual(services.recalculate_stock(product), 30)

    def test_low_stock_queryset(self):
        make_product(sku="LOW", stock=3, min_stock_alert=10)
        make_product(sku="FINE", stock=100, min_stock_alert=10)
        self.assertEqual([p.sku for p in Product.objects.low_stock()], ["LOW"])


class StockAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.warehouse = User.objects.create_user("wh", "wh@example.com", "pw", role="WAREHOUSE")
        self.sales = User.objects.create_user("sl", "sl@example.com", "pw", role="SALES")
        self.product = make_product(stock=20)

    def test_out_movement_beyond_stock_returns_400_with_details(self):
        self.client.force_authenticate(self.warehouse)
        response = self.client.post(
            "/api/stock-movements/",
            {"product": self.product.pk, "movement_type": "OUT", "quantity": 50, "reason": "DAMAGE"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["error"]["code"], "insufficient_stock")
        self.assertIn("shortages", response.data["error"]["details"])

    def test_sales_role_cannot_write_stock(self):
        self.client.force_authenticate(self.sales)
        response = self.client.post(
            "/api/stock-movements/",
            {"product": self.product.pk, "movement_type": "IN", "quantity": 5},
            format="json",
        )
        self.assertEqual(response.status_code, 403)

    def test_sales_role_can_read_stock(self):
        self.client.force_authenticate(self.sales)
        self.assertEqual(self.client.get("/api/stock-movements/").status_code, 200)

    def test_sale_reason_is_reserved_for_the_challan_workflow(self):
        self.client.force_authenticate(self.warehouse)
        response = self.client.post(
            "/api/stock-movements/",
            {"product": self.product.pk, "movement_type": "OUT", "quantity": 1, "reason": "SALE"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["error"]["code"], "validation_error")

    def test_creating_a_product_with_opening_stock_logs_a_movement(self):
        self.client.force_authenticate(self.warehouse)
        response = self.client.post(
            "/api/products/",
            {
                "name": "New Item",
                "sku": "new-1",
                "category": "Test",
                "unit_price": "10.00",
                "opening_stock": 12,
                "min_stock_alert": 2,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        product = Product.objects.get(sku="NEW-1")
        self.assertEqual(product.current_stock, 12)
        self.assertTrue(product.movements.filter(reason=MovementReason.OPENING).exists())

    def test_duplicate_sku_is_rejected(self):
        self.client.force_authenticate(self.warehouse)
        response = self.client.post(
            "/api/products/",
            {"name": "Clash", "sku": self.product.sku.lower(), "category": "Test", "unit_price": "1.00"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("sku", response.data["error"]["details"])

    def test_delete_archives_instead_of_removing(self):
        self.client.force_authenticate(self.warehouse)
        response = self.client.delete(f"/api/products/{self.product.pk}/")
        self.assertEqual(response.status_code, 204)
        self.product.refresh_from_db()
        self.assertFalse(self.product.is_active)

    def test_anonymous_access_is_rejected(self):
        self.assertEqual(self.client.get("/api/products/").status_code, 401)
