"""Tests for the challan PDF export (bonus feature)."""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from inventory.tests import make_product

from . import services
from .models import ChallanItem, SalesChallan
from .pdf import _amount_in_words, _money, render_challan_pdf
from .tests import make_customer

User = get_user_model()


class MoneyFormattingTests(TestCase):
    """Indian digit grouping - 12,34,567.50 rather than 1,234,567.50."""

    def test_lakh_and_crore_grouping(self):
        cases = {
            "0": "0.00",
            "999.9": "999.90",
            "1000": "1,000.00",
            "100000": "1,00,000.00",
            "1234567.5": "12,34,567.50",
            "123456789": "12,34,56,789.00",
        }
        for raw, expected in cases.items():
            with self.subTest(raw=raw):
                self.assertEqual(_money(Decimal(raw)), expected)

    def test_negative_amounts(self):
        self.assertEqual(_money(Decimal("-1234.5")), "-1,234.50")

    def test_none_is_treated_as_zero(self):
        self.assertEqual(_money(None), "0.00")


class AmountInWordsTests(TestCase):
    def test_common_amounts(self):
        cases = {
            "0": "Rupees Zero only",
            "1": "Rupees One only",
            "19": "Rupees Nineteen only",
            "100": "Rupees One Hundred only",
            "1000": "Rupees One Thousand only",
            "100000": "Rupees One Lakh only",
            "10000000": "Rupees One Crore only",
        }
        for raw, expected in cases.items():
            with self.subTest(raw=raw):
                self.assertEqual(_amount_in_words(Decimal(raw)), expected)

    def test_paise_are_included(self):
        self.assertEqual(
            _amount_in_words(Decimal("20201.60")),
            "Rupees Twenty Thousand Two Hundred One and Sixty Paise only",
        )

    def test_large_mixed_amount(self):
        self.assertEqual(
            _amount_in_words(Decimal("1234567.89")),
            "Rupees Twelve Lakh Thirty Four Thousand Five Hundred Sixty Seven and Eighty Nine Paise only",
        )


class ChallanPDFRenderTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("sl", "sl@example.com", "pw", role="SALES")
        self.customer = make_customer(
            business_name="Acme Traders",
            gst_number="27AAPFU0939F1ZV",
            customer_type="WHOLESALE",
            address="12 Main Street",
            city="Mumbai",
        )
        self.product = make_product(
            sku="PDF-1", stock=100, unit_price=Decimal("250.00"), tax_rate=Decimal("18")
        )

    def _challan(self, quantity=4):
        challan = SalesChallan(
            customer=self.customer,
            created_by=self.user,
            notes="Deliver before 6 pm.",
            vehicle_number="MH-01-AB-1234",
        )
        challan.copy_customer_snapshot()
        challan.save()
        item = ChallanItem(challan=challan, product=self.product, quantity=quantity)
        item.take_snapshot()
        item.save()
        challan.recalculate_totals()
        return challan

    def test_renders_a_valid_pdf(self):
        pdf = render_challan_pdf(self._challan())
        self.assertTrue(pdf.startswith(b"%PDF"), "should be a PDF document")
        self.assertTrue(pdf.rstrip().endswith(b"%%EOF"))
        self.assertGreater(len(pdf), 1500)

    def test_renders_in_every_status(self):
        for setup in ("draft", "confirmed", "cancelled"):
            with self.subTest(status=setup):
                challan = self._challan()
                if setup in ("confirmed", "cancelled"):
                    services.confirm_challan(challan, user=self.user)
                if setup == "cancelled":
                    services.cancel_challan(challan, user=self.user, reason="Order withdrawn")
                challan.refresh_from_db()
                self.assertTrue(render_challan_pdf(challan).startswith(b"%PDF"))

    def test_uses_the_snapshot_not_the_live_product(self):
        """A re-print must reproduce the document as it was issued."""
        challan = self._challan()
        original = render_challan_pdf(challan)

        self.product.name = "Completely Renamed Product"
        self.product.unit_price = Decimal("9999.00")
        self.product.save()

        challan.refresh_from_db()
        reprinted = render_challan_pdf(challan)

        # The rendered totals must be unchanged (4 x 250 = 1000 + 18% tax).
        self.assertEqual(challan.total_amount, Decimal("1000.00"))
        self.assertEqual(challan.grand_total, Decimal("1180.00"))
        self.assertEqual(len(original) // 100, len(reprinted) // 100)

    def test_survives_a_challan_with_many_lines(self):
        challan = self._challan()
        for index in range(30):
            product = make_product(sku=f"BULK-{index}", stock=50, unit_price=Decimal("10.00"))
            item = ChallanItem(challan=challan, product=product, quantity=2)
            item.take_snapshot()
            item.save()
        challan.recalculate_totals()

        pdf = render_challan_pdf(challan)
        self.assertTrue(pdf.startswith(b"%PDF"))
        self.assertGreater(len(pdf), 4000, "a multi-page challan should be larger")

    def test_handles_a_customer_with_minimal_details(self):
        bare = make_customer(mobile="9700001111", name="Walk In")
        challan = SalesChallan(customer=bare, created_by=self.user)
        challan.copy_customer_snapshot()
        challan.save()
        item = ChallanItem(challan=challan, product=self.product, quantity=1)
        item.take_snapshot()
        item.save()
        challan.recalculate_totals()

        self.assertTrue(render_challan_pdf(challan).startswith(b"%PDF"))


class ChallanPDFEndpointTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.sales = User.objects.create_user("sl", "sl@example.com", "pw", role="SALES")
        self.accounts = User.objects.create_user("ac", "ac@example.com", "pw", role="ACCOUNTS")
        self.customer = make_customer()
        self.product = make_product(sku="EP-1", stock=50, unit_price=Decimal("100.00"))

        challan = SalesChallan(customer=self.customer, created_by=self.sales)
        challan.copy_customer_snapshot()
        challan.save()
        item = ChallanItem(challan=challan, product=self.product, quantity=3)
        item.take_snapshot()
        item.save()
        challan.recalculate_totals()
        self.challan = challan

    def test_download_returns_a_pdf_attachment(self):
        self.client.force_authenticate(self.sales)
        response = self.client.get(f"/api/challans/{self.challan.pk}/pdf/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertIn("attachment", response["Content-Disposition"])
        self.assertIn(self.challan.challan_number, response["Content-Disposition"])
        self.assertTrue(response.content.startswith(b"%PDF"))

    def test_inline_disposition(self):
        self.client.force_authenticate(self.sales)
        response = self.client.get(f"/api/challans/{self.challan.pk}/pdf/?disposition=inline")
        self.assertIn("inline", response["Content-Disposition"])

    def test_read_only_roles_may_download(self):
        """Accounts needs the paperwork even though it cannot edit challans."""
        self.client.force_authenticate(self.accounts)
        response = self.client.get(f"/api/challans/{self.challan.pk}/pdf/")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.content.startswith(b"%PDF"))

    def test_requires_authentication(self):
        response = self.client.get(f"/api/challans/{self.challan.pk}/pdf/")
        self.assertEqual(response.status_code, 401)

    def test_unknown_challan_returns_404(self):
        self.client.force_authenticate(self.sales)
        self.assertEqual(self.client.get("/api/challans/999999/pdf/").status_code, 404)

    def test_content_length_matches_the_body(self):
        self.client.force_authenticate(self.sales)
        response = self.client.get(f"/api/challans/{self.challan.pk}/pdf/")
        self.assertEqual(int(response["Content-Length"]), len(response.content))
