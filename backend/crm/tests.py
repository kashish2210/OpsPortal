"""Customer CRM tests."""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from .models import Customer, CustomerStatus, CustomerType, FollowUp

User = get_user_model()


class CustomerModelTests(TestCase):
    def test_codes_are_generated_sequentially(self):
        first = Customer.objects.create(name="A", mobile="9800000001")
        second = Customer.objects.create(name="B", mobile="9800000002")
        self.assertEqual(first.code, "CUST-00001")
        self.assertEqual(second.code, "CUST-00002")

    def test_gst_and_email_are_normalised(self):
        customer = Customer.objects.create(
            name="A", mobile="9800000003", gst_number=" 27aapfu0939f1zv ", email=" A@B.COM "
        )
        self.assertEqual(customer.gst_number, "27AAPFU0939F1ZV")
        self.assertEqual(customer.email, "a@b.com")

    def test_follow_up_due_flag(self):
        today = timezone.localdate()
        due = Customer.objects.create(name="A", mobile="9800000004", follow_up_date=today)
        later = Customer.objects.create(
            name="B", mobile="9800000005", follow_up_date=today + timedelta(days=5)
        )
        self.assertTrue(due.is_follow_up_due)
        self.assertFalse(later.is_follow_up_due)

    def test_full_address_skips_blanks(self):
        customer = Customer.objects.create(
            name="A", mobile="9800000006", address="12 Main St", city="Pune", state="", pincode="411001"
        )
        self.assertEqual(customer.full_address, "12 Main St, Pune, 411001")

    def test_follow_up_pushes_the_next_date_onto_the_customer(self):
        customer = Customer.objects.create(name="A", mobile="9800000007")
        next_date = timezone.localdate() + timedelta(days=7)
        FollowUp.objects.create(customer=customer, note="Called", next_follow_up_date=next_date)

        customer.refresh_from_db()
        self.assertEqual(customer.follow_up_date, next_date)


class CustomerAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.sales = User.objects.create_user("sl", "sl@example.com", "pw", role="SALES")
        self.accounts = User.objects.create_user("ac", "ac@example.com", "pw", role="ACCOUNTS")
        self.client.force_authenticate(self.sales)

        self.customer = Customer.objects.create(
            name="Rajesh Kumar",
            business_name="Kumar Store",
            mobile="9820011223",
            city="Mumbai",
            status=CustomerStatus.ACTIVE,
        )

    def _payload(self, **overrides):
        return {
            "name": "New Customer",
            "mobile": "9899988877",
            "customer_type": CustomerType.RETAIL,
            "status": CustomerStatus.ACTIVE,
            **overrides,
        }

    def test_create_customer(self):
        response = self.client.post("/api/customers/", self._payload(), format="json")
        self.assertEqual(response.status_code, 201, response.data)
        self.assertTrue(response.data["code"].startswith("CUST-"))
        self.assertEqual(Customer.objects.get(pk=response.data["id"]).created_by, self.sales)

    def test_duplicate_mobile_is_rejected(self):
        response = self.client.post(
            "/api/customers/", self._payload(mobile=self.customer.mobile), format="json"
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("mobile", response.data["error"]["details"])

    def test_invalid_mobile_is_rejected(self):
        response = self.client.post("/api/customers/", self._payload(mobile="12"), format="json")
        self.assertEqual(response.status_code, 400)

    def test_wholesale_requires_gst(self):
        response = self.client.post(
            "/api/customers/", self._payload(customer_type=CustomerType.WHOLESALE), format="json"
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("gst_number", response.data["error"]["details"])

        response = self.client.post(
            "/api/customers/",
            self._payload(customer_type=CustomerType.WHOLESALE, gst_number="27AAPFU0939F1ZV"),
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)

    def test_malformed_gst_is_rejected(self):
        response = self.client.post(
            "/api/customers/",
            self._payload(customer_type=CustomerType.WHOLESALE, gst_number="NOTAGST"),
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_new_lead_requires_a_follow_up_date(self):
        response = self.client.post(
            "/api/customers/", self._payload(status=CustomerStatus.LEAD), format="json"
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("follow_up_date", response.data["error"]["details"])

    def test_search_matches_name_business_mobile_and_city(self):
        for term in ("Rajesh", "Kumar Store", "982001", "Mumbai"):
            with self.subTest(term=term):
                response = self.client.get("/api/customers/", {"q": term})
                self.assertEqual(response.data["count"], 1, term)

    def test_filter_by_status_and_type(self):
        Customer.objects.create(
            name="Lead One",
            mobile="9700000001",
            status=CustomerStatus.LEAD,
            customer_type=CustomerType.RETAIL,
        )
        self.assertEqual(self.client.get("/api/customers/?status=LEAD").data["count"], 1)
        self.assertEqual(self.client.get("/api/customers/?status=ACTIVE").data["count"], 1)

    def test_follow_up_due_filter(self):
        Customer.objects.create(
            name="Due", mobile="9700000002", follow_up_date=timezone.localdate() - timedelta(days=1)
        )
        Customer.objects.create(
            name="Later", mobile="9700000003", follow_up_date=timezone.localdate() + timedelta(days=9)
        )
        self.assertEqual(self.client.get("/api/customers/?follow_up=due").data["count"], 1)
        self.assertEqual(self.client.get("/api/customers/?follow_up=upcoming").data["count"], 1)

    def test_add_follow_up_note(self):
        next_date = (timezone.localdate() + timedelta(days=4)).isoformat()
        response = self.client.post(
            f"/api/customers/{self.customer.pk}/follow-ups/",
            {
                "note": "Spoke to the owner about the new rate card.",
                "channel": "CALL",
                "next_follow_up_date": next_date,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["created_by_name"], self.sales.display_name)

        self.customer.refresh_from_db()
        self.assertEqual(self.customer.follow_up_date.isoformat(), next_date)

    def test_follow_up_note_must_be_meaningful(self):
        response = self.client.post(
            f"/api/customers/{self.customer.pk}/follow-ups/", {"note": "ok"}, format="json"
        )
        self.assertEqual(response.status_code, 400)

    def test_follow_up_date_cannot_be_in_the_past(self):
        response = self.client.post(
            f"/api/customers/{self.customer.pk}/follow-ups/",
            {
                "note": "Called the shop today.",
                "next_follow_up_date": (timezone.localdate() - timedelta(days=1)).isoformat(),
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_detail_includes_recent_follow_ups(self):
        FollowUp.objects.create(customer=self.customer, note="First contact made.")
        response = self.client.get(f"/api/customers/{self.customer.pk}/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["recent_follow_ups"]), 1)
        self.assertEqual(response.data["follow_up_count"], 1)

    def test_delete_archives_the_customer(self):
        response = self.client.delete(f"/api/customers/{self.customer.pk}/")
        self.assertEqual(response.status_code, 204)
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.status, CustomerStatus.INACTIVE)

    def test_accounts_role_is_read_only(self):
        self.client.force_authenticate(self.accounts)
        self.assertEqual(self.client.get("/api/customers/").status_code, 200)
        self.assertEqual(self.client.post("/api/customers/", self._payload(), format="json").status_code, 403)

    def test_stats_endpoint(self):
        response = self.client.get("/api/customers/stats/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["total"], 1)
        self.assertEqual(response.data["active"], 1)

    def test_options_endpoint_excludes_inactive_customers(self):
        Customer.objects.create(name="Gone", mobile="9700000004", status=CustomerStatus.INACTIVE)
        response = self.client.get("/api/customers/options/")
        self.assertEqual(len(response.data), 1)
