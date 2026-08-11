"""Sales challan workflow tests."""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from core.exceptions import BusinessRuleError, InsufficientStockError
from crm.models import Customer, CustomerStatus, CustomerType
from inventory.models import MovementReason, MovementType, StockMovement
from inventory.tests import make_product

from . import services
from .models import ChallanItem, ChallanStatus, SalesChallan

User = get_user_model()


def make_customer(mobile="9800000001", **kwargs):
    return Customer.objects.create(
        name=kwargs.pop("name", "Test Customer"),
        mobile=mobile,
        customer_type=kwargs.pop("customer_type", CustomerType.RETAIL),
        status=kwargs.pop("status", CustomerStatus.ACTIVE),
        **kwargs,
    )


class ChallanNumberingTests(TestCase):
    def test_numbers_are_sequential_and_month_scoped(self):
        first = SalesChallan.generate_number(timezone.localdate())
        second = SalesChallan.generate_number(timezone.localdate())
        period = timezone.localdate().strftime("%Y%m")

        self.assertEqual(first, f"CH-{period}-00001")
        self.assertEqual(second, f"CH-{period}-00002")

    def test_the_counter_restarts_each_month(self):
        import datetime

        jan = SalesChallan.generate_number(datetime.date(2026, 1, 15))
        feb = SalesChallan.generate_number(datetime.date(2026, 2, 1))
        self.assertEqual(jan, "CH-202601-00001")
        self.assertEqual(feb, "CH-202602-00001")


class ChallanServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("sl", "sl@example.com", "pw", role="SALES")
        self.customer = make_customer()
        self.product = make_product(sku="P-1", stock=100, unit_price=Decimal("50.00"))
        self.other = make_product(sku="P-2", stock=3, unit_price=Decimal("20.00"))

    def _draft(self, lines=None):
        challan = SalesChallan(customer=self.customer, created_by=self.user)
        challan.copy_customer_snapshot()
        challan.save()
        for product, quantity in lines or [(self.product, 10)]:
            item = ChallanItem(challan=challan, product=product, quantity=quantity)
            item.take_snapshot()
            item.save()
        challan.recalculate_totals()
        return challan

    def test_draft_does_not_touch_stock(self):
        self._draft()
        self.product.refresh_from_db()
        self.assertEqual(self.product.current_stock, 100)
        self.assertEqual(StockMovement.objects.filter(reason=MovementReason.SALE).count(), 0)

    def test_confirm_reduces_stock_and_writes_out_movements(self):
        challan = self._draft([(self.product, 10)])
        services.confirm_challan(challan, user=self.user)

        challan.refresh_from_db()
        self.product.refresh_from_db()

        self.assertEqual(challan.status, ChallanStatus.CONFIRMED)
        self.assertEqual(challan.confirmed_by, self.user)
        self.assertIsNotNone(challan.confirmed_at)
        self.assertEqual(self.product.current_stock, 90)

        movement = StockMovement.objects.get(reason=MovementReason.SALE)
        self.assertEqual(movement.movement_type, MovementType.OUT)
        self.assertEqual(movement.quantity, 10)
        self.assertEqual(movement.reference, challan.challan_number)
        self.assertEqual(movement.balance_after, 90)

    def test_confirm_fails_when_stock_is_short_and_changes_nothing(self):
        challan = self._draft([(self.product, 5), (self.other, 10)])

        with self.assertRaises(InsufficientStockError) as ctx:
            services.confirm_challan(challan, user=self.user)

        shortages = ctx.exception.details["shortages"]
        self.assertEqual([s["sku"] for s in shortages], ["P-2"])
        self.assertEqual(shortages[0]["short_by"], 7)

        challan.refresh_from_db()
        self.product.refresh_from_db()
        self.assertEqual(challan.status, ChallanStatus.DRAFT)
        self.assertEqual(self.product.current_stock, 100, "the fulfillable line must roll back too")

    def test_confirming_twice_is_refused(self):
        challan = self._draft()
        services.confirm_challan(challan, user=self.user)
        with self.assertRaises(BusinessRuleError) as ctx:
            services.confirm_challan(challan, user=self.user)
        self.assertEqual(ctx.exception.get_codes(), "already_confirmed")

    def test_empty_challan_cannot_be_confirmed(self):
        challan = SalesChallan(customer=self.customer, created_by=self.user)
        challan.copy_customer_snapshot()
        challan.save()
        with self.assertRaises(BusinessRuleError) as ctx:
            services.confirm_challan(challan, user=self.user)
        self.assertEqual(ctx.exception.get_codes(), "empty_challan")

    def test_cancelling_a_confirmed_challan_returns_the_stock(self):
        challan = self._draft([(self.product, 30)])
        services.confirm_challan(challan, user=self.user)
        self.product.refresh_from_db()
        self.assertEqual(self.product.current_stock, 70)

        services.cancel_challan(challan, user=self.user, reason="Customer changed their mind")

        challan.refresh_from_db()
        self.product.refresh_from_db()
        self.assertEqual(challan.status, ChallanStatus.CANCELLED)
        self.assertEqual(challan.cancellation_reason, "Customer changed their mind")
        self.assertEqual(self.product.current_stock, 100)
        self.assertTrue(
            StockMovement.objects.filter(
                reason=MovementReason.CHALLAN_CANCELLED, movement_type=MovementType.IN
            ).exists()
        )

    def test_cancelling_a_draft_leaves_stock_alone(self):
        challan = self._draft()
        services.cancel_challan(challan, user=self.user)
        self.product.refresh_from_db()
        self.assertEqual(self.product.current_stock, 100)
        self.assertEqual(StockMovement.objects.filter(reason=MovementReason.SALE).count(), 0)

    def test_cancelling_twice_is_refused(self):
        challan = self._draft()
        services.cancel_challan(challan, user=self.user)
        with self.assertRaises(BusinessRuleError):
            services.cancel_challan(challan, user=self.user)

    def test_cancelled_challan_cannot_be_confirmed(self):
        challan = self._draft()
        services.cancel_challan(challan, user=self.user)
        with self.assertRaises(BusinessRuleError) as ctx:
            services.confirm_challan(challan, user=self.user)
        self.assertEqual(ctx.exception.get_codes(), "challan_cancelled")


class ChallanSnapshotTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("sl", "sl@example.com", "pw", role="SALES")
        self.customer = make_customer(
            business_name="Acme Traders", gst_number="27AAPFU0939F1ZV", customer_type=CustomerType.WHOLESALE
        )
        self.product = make_product(sku="SNAP-1", stock=50, unit_price=Decimal("200.00"))

    def test_line_stores_a_product_snapshot(self):
        challan = SalesChallan(customer=self.customer, created_by=self.user)
        challan.copy_customer_snapshot()
        challan.save()
        item = ChallanItem(challan=challan, product=self.product, quantity=2)
        item.take_snapshot()
        item.save()

        self.assertEqual(item.product_sku, "SNAP-1")
        self.assertEqual(item.unit_price, Decimal("200.00"))
        self.assertEqual(item.line_total, Decimal("400.00"))

    def test_renaming_and_repricing_a_product_does_not_rewrite_history(self):
        challan = SalesChallan(customer=self.customer, created_by=self.user)
        challan.copy_customer_snapshot()
        challan.save()
        item = ChallanItem(challan=challan, product=self.product, quantity=2)
        item.take_snapshot()
        item.save()

        self.product.name = "Renamed Product"
        self.product.unit_price = Decimal("999.00")
        self.product.save()

        item.refresh_from_db()
        self.assertNotEqual(item.product_name, "Renamed Product")
        self.assertEqual(item.unit_price, Decimal("200.00"))
        self.assertEqual(item.line_total, Decimal("400.00"))

    def test_customer_snapshot_survives_customer_edits(self):
        challan = SalesChallan(customer=self.customer, created_by=self.user)
        challan.copy_customer_snapshot()
        challan.save()

        self.customer.business_name = "Renamed Traders"
        self.customer.save()

        challan.refresh_from_db()
        self.assertEqual(challan.customer_business_name, "Acme Traders")

    def test_totals_include_tax(self):
        product = make_product(sku="TAX-1", stock=10, unit_price=Decimal("100.00"), tax_rate=Decimal("18"))
        challan = SalesChallan(customer=self.customer, created_by=self.user)
        challan.copy_customer_snapshot()
        challan.save()
        item = ChallanItem(challan=challan, product=product, quantity=3)
        item.take_snapshot()
        item.save()
        challan.recalculate_totals()

        self.assertEqual(challan.total_quantity, 3)
        self.assertEqual(challan.total_amount, Decimal("300.00"))
        self.assertEqual(challan.total_tax, Decimal("54.00"))
        self.assertEqual(challan.grand_total, Decimal("354.00"))


class ChallanAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.sales = User.objects.create_user("sl", "sl@example.com", "pw", role="SALES")
        self.warehouse = User.objects.create_user("wh", "wh@example.com", "pw", role="WAREHOUSE")
        self.customer = make_customer()
        self.product = make_product(sku="API-1", stock=20, unit_price=Decimal("10.00"))
        self.client.force_authenticate(self.sales)

    def _create(self, payload=None, **overrides):
        body = {
            "customer": self.customer.pk,
            "items": [{"product": self.product.pk, "quantity": 5}],
            **(payload or {}),
            **overrides,
        }
        return self.client.post("/api/challans/", body, format="json")

    def test_create_draft(self):
        response = self._create()
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["status"], "DRAFT")
        self.assertTrue(response.data["challan_number"].startswith("CH-"))
        self.assertEqual(response.data["total_quantity"], 5)

        self.product.refresh_from_db()
        self.assertEqual(self.product.current_stock, 20)

    def test_create_and_confirm_in_one_request(self):
        response = self._create(confirm=True)
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["status"], "CONFIRMED")

        self.product.refresh_from_db()
        self.assertEqual(self.product.current_stock, 15)

    def test_save_and_confirm_rolls_back_completely_when_stock_is_short(self):
        response = self._create({"items": [{"product": self.product.pk, "quantity": 500}]}, confirm=True)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["error"]["code"], "insufficient_stock")
        self.assertEqual(SalesChallan.objects.count(), 0, "no orphan draft may survive")

        self.product.refresh_from_db()
        self.assertEqual(self.product.current_stock, 20)

    def test_confirm_endpoint(self):
        challan_id = self._create().data["id"]
        response = self.client.post(f"/api/challans/{challan_id}/confirm/")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["status"], "CONFIRMED")

    def test_confirm_endpoint_reports_shortages(self):
        challan_id = self._create({"items": [{"product": self.product.pk, "quantity": 5}]}).data["id"]
        # Drain the warehouse behind the draft's back.
        from inventory import services as stock_services

        stock_services.apply_movement(
            product=self.product, quantity=18, movement_type=MovementType.OUT, user=self.warehouse
        )

        response = self.client.post(f"/api/challans/{challan_id}/confirm/")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["error"]["code"], "insufficient_stock")
        shortage = response.data["error"]["details"]["shortages"][0]
        self.assertEqual(shortage["requested"], 5)
        self.assertEqual(shortage["available"], 2)

    def test_confirmed_challan_cannot_be_edited(self):
        challan_id = self._create(confirm=True).data["id"]
        response = self.client.patch(f"/api/challans/{challan_id}/", {"notes": "changed"}, format="json")
        self.assertEqual(response.status_code, 400)

    def test_confirmed_challan_cannot_be_deleted(self):
        challan_id = self._create(confirm=True).data["id"]
        response = self.client.delete(f"/api/challans/{challan_id}/")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["error"]["code"], "challan_not_editable")

    def test_draft_can_be_edited_and_lines_replaced(self):
        challan_id = self._create().data["id"]
        response = self.client.patch(
            f"/api/challans/{challan_id}/",
            {"items": [{"product": self.product.pk, "quantity": 9}], "notes": "updated"},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["total_quantity"], 9)
        self.assertEqual(len(response.data["items"]), 1)

    def test_cancel_endpoint_restores_stock(self):
        challan_id = self._create(confirm=True).data["id"]
        response = self.client.post(
            f"/api/challans/{challan_id}/cancel/", {"reason": "Order withdrawn"}, format="json"
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["status"], "CANCELLED")

        self.product.refresh_from_db()
        self.assertEqual(self.product.current_stock, 20)

    def test_duplicate_product_lines_are_rejected(self):
        response = self._create(
            {
                "items": [
                    {"product": self.product.pk, "quantity": 1},
                    {"product": self.product.pk, "quantity": 2},
                ]
            }
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("items", response.data["error"]["details"])

    def test_challan_without_lines_is_rejected(self):
        response = self._create({"items": []})
        self.assertEqual(response.status_code, 400)

    def test_inactive_customer_is_rejected(self):
        self.customer.status = CustomerStatus.INACTIVE
        self.customer.save()
        response = self._create()
        self.assertEqual(response.status_code, 400)
        self.assertIn("customer", response.data["error"]["details"])

    def test_warehouse_role_can_read_but_not_create_challans(self):
        self.client.force_authenticate(self.warehouse)
        self.assertEqual(self.client.get("/api/challans/").status_code, 200)
        self.assertEqual(self._create().status_code, 403)

    def test_zero_quantity_is_rejected(self):
        response = self._create({"items": [{"product": self.product.pk, "quantity": 0}]})
        self.assertEqual(response.status_code, 400)

    def test_line_price_can_be_overridden(self):
        response = self._create(
            {"items": [{"product": self.product.pk, "quantity": 2, "unit_price": "7.50"}]}
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(Decimal(response.data["items"][0]["unit_price"]), Decimal("7.50"))
        self.assertEqual(Decimal(response.data["total_amount"]), Decimal("15.00"))

    def test_stock_movements_endpoint_lists_the_challan_ledger(self):
        challan_id = self._create(confirm=True).data["id"]
        response = self.client.get(f"/api/challans/{challan_id}/stock-movements/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["reason"], MovementReason.SALE)

    def test_filtering_by_status_and_search(self):
        self._create()
        self._create(confirm=True)
        self.assertEqual(self.client.get("/api/challans/?status=DRAFT").data["count"], 1)
        self.assertEqual(self.client.get("/api/challans/?status=CONFIRMED").data["count"], 1)
        self.assertEqual(self.client.get("/api/challans/?q=API-1").data["count"], 2)

    def test_pagination_envelope(self):
        self._create()
        payload = self.client.get("/api/challans/?page_size=1").data
        for key in ("count", "page", "page_size", "total_pages", "results"):
            self.assertIn(key, payload)
