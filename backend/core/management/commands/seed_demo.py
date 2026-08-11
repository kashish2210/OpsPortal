"""Populate the database with a realistic demo dataset.

    python manage.py seed_demo            # idempotent, skips if data exists
    python manage.py seed_demo --reset    # wipe business data first
    python manage.py seed_demo --force    # top up even if data exists

Creates one login per role, a customer book, a product catalogue with stock,
follow-up notes and challans in every state (draft / confirmed / cancelled).
"""

import random
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from crm.models import Customer, CustomerStatus, CustomerType, FollowUp, FollowUpChannel
from inventory import services as stock_services
from inventory.models import MovementReason, MovementType, Product, StockMovement, UnitOfMeasure
from sales import services as sales_services
from sales.models import ChallanItem, SalesChallan

User = get_user_model()

DEMO_USERS = [
    {
        "username": "admin",
        "email": "admin@opsportal.local",
        "password": "Admin@12345",
        "role": "ADMIN",
        "first_name": "Aarav",
        "last_name": "Mehta",
        "department": "Management",
        "is_staff": True,
        "is_superuser": True,
    },
    {
        "username": "sales",
        "email": "sales@opsportal.local",
        "password": "Sales@12345",
        "role": "SALES",
        "first_name": "Riya",
        "last_name": "Sharma",
        "department": "Sales",
    },
    {
        "username": "warehouse",
        "email": "warehouse@opsportal.local",
        "password": "Warehouse@12345",
        "role": "WAREHOUSE",
        "first_name": "Imran",
        "last_name": "Qureshi",
        "department": "Warehouse",
    },
    {
        "username": "accounts",
        "email": "accounts@opsportal.local",
        "password": "Accounts@12345",
        "role": "ACCOUNTS",
        "first_name": "Neha",
        "last_name": "Patel",
        "department": "Accounts",
    },
]

CUSTOMERS = [
    (
        "Rajesh Kumar",
        "Kumar General Store",
        "9820011223",
        "rajesh@kumarstore.in",
        "27AAPFU0939F1ZV",
        CustomerType.RETAIL,
        CustomerStatus.ACTIVE,
        "Shop 14, Linking Road",
        "Mumbai",
        "Maharashtra",
        "400050",
    ),
    (
        "Sunita Desai",
        "Desai Wholesale Mart",
        "9820011224",
        "sunita@desaimart.in",
        "27AACCD1234E1Z5",
        CustomerType.WHOLESALE,
        CustomerStatus.ACTIVE,
        "Plot 8, MIDC Andheri",
        "Mumbai",
        "Maharashtra",
        "400093",
    ),
    (
        "Vikram Singh",
        "Singh Distributors Pvt Ltd",
        "9811022334",
        "vikram@singhdist.co.in",
        "07AABCS4567H1Z2",
        CustomerType.DISTRIBUTOR,
        CustomerStatus.ACTIVE,
        "B-45, Okhla Phase II",
        "New Delhi",
        "Delhi",
        "110020",
    ),
    (
        "Anita Rao",
        "Rao Provisions",
        "9845033445",
        "anita.rao@gmail.com",
        "",
        CustomerType.RETAIL,
        CustomerStatus.LEAD,
        "22 Church Street",
        "Bengaluru",
        "Karnataka",
        "560001",
    ),
    (
        "Mohammed Farooq",
        "Farooq Traders",
        "9840044556",
        "farooq@farooqtraders.in",
        "33AAECF7890K1Z8",
        CustomerType.WHOLESALE,
        CustomerStatus.ACTIVE,
        "12 NSC Bose Road",
        "Chennai",
        "Tamil Nadu",
        "600001",
    ),
    (
        "Priya Nair",
        "Nair Super Bazaar",
        "9847055667",
        "priya@nairbazaar.in",
        "",
        CustomerType.RETAIL,
        CustomerStatus.ACTIVE,
        "MG Road, Ravipuram",
        "Kochi",
        "Kerala",
        "682015",
    ),
    (
        "Harpreet Gill",
        "Gill Agencies",
        "9878066778",
        "gill.agencies@outlook.com",
        "03AADCG2345L1Z1",
        CustomerType.DISTRIBUTOR,
        CustomerStatus.ACTIVE,
        "SCO 112, Sector 34A",
        "Chandigarh",
        "Punjab",
        "160022",
    ),
    (
        "Deepak Joshi",
        "Joshi Kirana",
        "9825077889",
        "",
        "",
        CustomerType.RETAIL,
        CustomerStatus.LEAD,
        "Near Bus Stand, Navrangpura",
        "Ahmedabad",
        "Gujarat",
        "380009",
    ),
    (
        "Kavita Bhatt",
        "Bhatt Home Needs",
        "9826088990",
        "kavita@bhatthome.in",
        "",
        CustomerType.RETAIL,
        CustomerStatus.INACTIVE,
        "45 Sarafa Bazaar",
        "Indore",
        "Madhya Pradesh",
        "452002",
    ),
    (
        "Sanjay Reddy",
        "Reddy Wholesale Hub",
        "9866099001",
        "sanjay@reddyhub.in",
        "36AAFCR6789M1Z4",
        CustomerType.WHOLESALE,
        CustomerStatus.ACTIVE,
        "Road No 12, Banjara Hills",
        "Hyderabad",
        "Telangana",
        "500034",
    ),
    (
        "Meera Iyer",
        "Iyer Stores",
        "9884010112",
        "meera.iyer@yahoo.in",
        "",
        CustomerType.RETAIL,
        CustomerStatus.LEAD,
        "7 Gandhi Nagar",
        "Coimbatore",
        "Tamil Nadu",
        "641012",
    ),
    (
        "Arjun Chatterjee",
        "Chatterjee Enterprises",
        "9831021223",
        "arjun@chatterjee-ent.in",
        "19AAJCC3456N1Z7",
        CustomerType.DISTRIBUTOR,
        CustomerStatus.ACTIVE,
        "18 Park Street",
        "Kolkata",
        "West Bengal",
        "700016",
    ),
]

PRODUCTS = [
    # name, sku, category, unit, price, tax, opening stock, min alert, location, hsn
    (
        "Copper Wire 1.5mm (90m)",
        "EL-CW15-90",
        "Electrical",
        UnitOfMeasure.PCS,
        "1180.00",
        18,
        140,
        25,
        "Warehouse A - Rack 1",
        "8544",
    ),
    (
        "Copper Wire 2.5mm (90m)",
        "EL-CW25-90",
        "Electrical",
        UnitOfMeasure.PCS,
        "1890.00",
        18,
        96,
        20,
        "Warehouse A - Rack 1",
        "8544",
    ),
    (
        "LED Panel Light 18W",
        "EL-LED-18",
        "Electrical",
        UnitOfMeasure.PCS,
        "340.00",
        18,
        420,
        60,
        "Warehouse A - Rack 2",
        "9405",
    ),
    (
        "Modular Switch 6A",
        "EL-SW-6A",
        "Electrical",
        UnitOfMeasure.PCS,
        "95.00",
        18,
        18,
        50,
        "Warehouse A - Rack 3",
        "8536",
    ),
    (
        "MCB 32A Single Pole",
        "EL-MCB-32",
        "Electrical",
        UnitOfMeasure.PCS,
        "265.00",
        18,
        210,
        40,
        "Warehouse A - Rack 3",
        "8536",
    ),
    (
        "PVC Conduit Pipe 25mm",
        "HW-PVC-25",
        "Hardware",
        UnitOfMeasure.MTR,
        "42.00",
        18,
        1800,
        300,
        "Warehouse B - Bay 1",
        "3917",
    ),
    (
        "GI Pipe 1 inch (6m)",
        "HW-GI-1IN",
        "Hardware",
        UnitOfMeasure.PCS,
        "760.00",
        18,
        88,
        20,
        "Warehouse B - Bay 2",
        "7306",
    ),
    (
        "Ball Bearing 6203ZZ",
        "HW-BB-6203",
        "Hardware",
        UnitOfMeasure.PCS,
        "118.00",
        18,
        640,
        100,
        "Warehouse B - Bay 3",
        "8482",
    ),
    (
        "Hex Bolt M10 x 50 (100 pc)",
        "HW-HB-M1050",
        "Hardware",
        UnitOfMeasure.BOX,
        "480.00",
        18,
        130,
        30,
        "Warehouse B - Bay 3",
        "7318",
    ),
    (
        "Wall Putty 20kg",
        "PT-WP-20",
        "Paints",
        UnitOfMeasure.PKT,
        "620.00",
        18,
        240,
        50,
        "Warehouse C - Row 1",
        "3214",
    ),
    (
        "Emulsion Paint White 20L",
        "PT-EM-W20",
        "Paints",
        UnitOfMeasure.PCS,
        "3450.00",
        18,
        62,
        15,
        "Warehouse C - Row 1",
        "3209",
    ),
    (
        "Primer Coat 10L",
        "PT-PR-10",
        "Paints",
        UnitOfMeasure.PCS,
        "1280.00",
        18,
        9,
        20,
        "Warehouse C - Row 2",
        "3208",
    ),
    (
        "Cotton Waste 50kg",
        "PK-CW-50",
        "Packaging",
        UnitOfMeasure.KG,
        "78.00",
        5,
        900,
        150,
        "Warehouse D",
        "5202",
    ),
    (
        "Corrugated Box 12x10x8",
        "PK-CB-1210",
        "Packaging",
        UnitOfMeasure.PCS,
        "26.00",
        12,
        3200,
        500,
        "Warehouse D",
        "4819",
    ),
    (
        "Stretch Wrap Film 2kg",
        "PK-SW-2",
        "Packaging",
        UnitOfMeasure.PCS,
        "295.00",
        18,
        155,
        40,
        "Warehouse D",
        "3920",
    ),
    (
        "Safety Helmet (Yellow)",
        "SF-HL-Y",
        "Safety",
        UnitOfMeasure.PCS,
        "310.00",
        18,
        275,
        50,
        "Warehouse A - Rack 4",
        "6506",
    ),
    (
        "Cut-resistant Gloves (Pair)",
        "SF-GL-CR",
        "Safety",
        UnitOfMeasure.PCS,
        "185.00",
        18,
        0,
        60,
        "Warehouse A - Rack 4",
        "6116",
    ),
    (
        "Industrial Adhesive 1kg",
        "CH-AD-1",
        "Chemicals",
        UnitOfMeasure.KG,
        "540.00",
        18,
        118,
        25,
        "Warehouse C - Row 3",
        "3506",
    ),
    (
        "Lubricant Oil 5L",
        "CH-LO-5",
        "Chemicals",
        UnitOfMeasure.LTR,
        "1120.00",
        18,
        74,
        20,
        "Warehouse C - Row 3",
        "2710",
    ),
    (
        "Cleaning Solvent 20L",
        "CH-CS-20",
        "Chemicals",
        UnitOfMeasure.LTR,
        "2260.00",
        18,
        31,
        10,
        "Warehouse C - Row 3",
        "3814",
    ),
]

FOLLOW_UP_NOTES = [
    "Called to confirm the monthly requirement. Wants a revised rate card.",
    "Visited the shop - stock of LED panels running low, expects an order next week.",
    "Sent the catalogue over WhatsApp. Asked for bulk pricing on packaging items.",
    "Payment for the last challan cleared. Happy with the delivery timing.",
    "Requested a sample of the new safety gloves before committing.",
    "Wants delivery shifted to mornings; noted for the warehouse team.",
    "Discussed credit terms - asked for 30 days instead of 15.",
    "Follow-up call: comparing our rates with a competitor, needs a response.",
]


class Command(BaseCommand):
    help = "Seed the database with demo users, customers, products and challans."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Delete existing business data (challans, products, customers) first.",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Seed even if data already exists.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        random.seed(20260810)  # deterministic demo data

        if options["reset"]:
            self.stdout.write(self.style.WARNING("Deleting existing business data..."))
            ChallanItem.objects.all().delete()
            SalesChallan.objects.all().delete()
            StockMovement.objects.all().delete()
            Product.objects.all().delete()
            FollowUp.objects.all().delete()
            Customer.objects.all().delete()

        users = self._seed_users()

        if Customer.objects.exists() and not (options["force"] or options["reset"]):
            self.stdout.write(
                self.style.WARNING(
                    "Business data already present - skipping. Use --force or --reset to re-seed."
                )
            )
            self._print_credentials()
            return

        customers = self._seed_customers(users["sales"])
        products = self._seed_products(users["warehouse"])
        self._seed_follow_ups(customers, users["sales"])
        # Each follow-up note pushes the customer's next-contact date forward,
        # so re-apply the intended spread afterwards - otherwise nothing is
        # ever overdue and the CRM dashboard looks empty.
        self._apply_follow_up_spread(customers)
        self._seed_challans(customers, products, users)

        self.stdout.write(self.style.SUCCESS("\nDemo data seeded successfully."))
        self._print_summary()
        self._print_credentials()

    # -- steps -------------------------------------------------------------
    def _seed_users(self):
        created = {}
        for spec in DEMO_USERS:
            spec = dict(spec)
            password = spec.pop("password")
            user, was_new = User.objects.get_or_create(
                username=spec["username"],
                defaults={**spec, "is_email_verified": True},
            )
            if was_new:
                user.set_password(password)
                user.save()
                self.stdout.write(f"  + user {user.username} ({user.get_role_display()})")
            created[spec["role"].lower()] = user
        return created

    def _seed_customers(self, owner):
        today = timezone.localdate()
        customers = []
        for index, row in enumerate(CUSTOMERS):
            (name, business, mobile, email, gst, ctype, cstatus, address, city, state, pincode) = row

            follow_up = None
            if cstatus != CustomerStatus.INACTIVE:
                # A spread of overdue, due-today and upcoming follow-ups.
                offset = [-6, -2, 0, 1, 3, 8, 14][index % 7]
                follow_up = today + timedelta(days=offset)

            customer, _ = Customer.objects.get_or_create(
                mobile=mobile,
                defaults={
                    "name": name,
                    "business_name": business,
                    "email": email,
                    "gst_number": gst,
                    "customer_type": ctype,
                    "status": cstatus,
                    "address": address,
                    "city": city,
                    "state": state,
                    "pincode": pincode,
                    "credit_limit": Decimal(random.choice(["0", "25000", "50000", "100000"])),
                    "follow_up_date": follow_up,
                    "notes": "Imported from the legacy spreadsheet during onboarding.",
                    "created_by": owner,
                    "updated_by": owner,
                },
            )
            customers.append(customer)
        self.stdout.write(f"  + {len(customers)} customers")
        return customers

    def _seed_products(self, owner):
        products = []
        for name, sku, category, unit, price, tax, opening, min_alert, location, hsn in PRODUCTS:
            product, was_new = Product.objects.get_or_create(
                sku=sku,
                defaults={
                    "name": name,
                    "category": category,
                    "unit": unit,
                    "unit_price": Decimal(price),
                    "tax_rate": Decimal(tax),
                    "min_stock_alert": min_alert,
                    "location": location,
                    "hsn_code": hsn,
                    "description": f"{name} - standard grade, sold by {unit}.",
                    "created_by": owner,
                    "updated_by": owner,
                },
            )
            if was_new and opening:
                stock_services.apply_movement(
                    product=product,
                    quantity=opening,
                    movement_type=MovementType.IN,
                    reason=MovementReason.OPENING,
                    user=owner,
                    notes="Opening balance loaded during go-live.",
                )
                product.refresh_from_db()
            products.append(product)

        # A couple of extra movements so the ledger looks lived-in.
        restock = products[3]  # Modular Switch - deliberately below its alert level
        stock_services.apply_movement(
            product=restock,
            quantity=12,
            movement_type=MovementType.IN,
            reason=MovementReason.PURCHASE,
            user=owner,
            reference="PO-2026-0043",
            notes="Partial delivery against purchase order.",
        )
        damaged = products[10]
        stock_services.apply_movement(
            product=damaged,
            quantity=2,
            movement_type=MovementType.OUT,
            reason=MovementReason.DAMAGE,
            user=owner,
            notes="Two tins dented in transit; written off.",
        )

        self.stdout.write(f"  + {len(products)} products with opening stock")
        return products

    def _seed_follow_ups(self, customers, owner):
        count = 0
        today = timezone.localdate()
        for customer in customers:
            if customer.status == CustomerStatus.INACTIVE:
                continue
            for _ in range(random.randint(1, 3)):
                FollowUp.objects.create(
                    customer=customer,
                    note=random.choice(FOLLOW_UP_NOTES),
                    channel=random.choice(list(FollowUpChannel.values)),
                    next_follow_up_date=today + timedelta(days=random.randint(2, 21)),
                    created_by=owner,
                )
                count += 1
        self.stdout.write(f"  + {count} follow-up notes")

    def _apply_follow_up_spread(self, customers):
        """Give the demo a realistic mix of overdue, due-today and upcoming."""
        today = timezone.localdate()
        offsets = [-6, -2, 0, 1, 3, 8, 14]
        overdue = 0
        for index, customer in enumerate(customers):
            if customer.status == CustomerStatus.INACTIVE:
                continue
            follow_up = today + timedelta(days=offsets[index % len(offsets)])
            Customer.objects.filter(pk=customer.pk).update(
                follow_up_date=follow_up, updated_at=timezone.now()
            )
            customer.follow_up_date = follow_up
            if follow_up <= today:
                overdue += 1
        self.stdout.write(f"  + {overdue} customers with a follow-up due today or overdue")

    def _seed_challans(self, customers, products, users):
        sales_user = users["sales"]
        today = timezone.localdate()
        sellable = [p for p in products if p.current_stock > 20]
        active_customers = [c for c in customers if c.status == CustomerStatus.ACTIVE]

        confirmed = drafts = cancelled = 0

        # Six confirmed challans spread over the last fortnight.
        for offset in range(6):
            customer = active_customers[offset % len(active_customers)]
            challan = SalesChallan(
                customer=customer,
                challan_date=today - timedelta(days=offset * 2),
                created_by=sales_user,
                notes="Standard delivery. Call the shop before dispatch.",
                vehicle_number=f"MH-01-AB-{1000 + offset}",
            )
            challan.copy_customer_snapshot()
            challan.save()

            for product in random.sample(sellable, random.randint(2, 4)):
                item = ChallanItem(challan=challan, product=product, quantity=random.randint(2, 12))
                item.take_snapshot()
                item.save()
            challan.recalculate_totals()
            sales_services.confirm_challan(challan, user=sales_user)
            confirmed += 1

        # Two drafts still being worked on.
        for offset in range(2):
            customer = active_customers[(offset + 3) % len(active_customers)]
            challan = SalesChallan(
                customer=customer,
                challan_date=today,
                created_by=sales_user,
                notes="Awaiting confirmation from the customer on quantities.",
            )
            challan.copy_customer_snapshot()
            challan.save()
            for product in random.sample(sellable, 2):
                item = ChallanItem(challan=challan, product=product, quantity=random.randint(1, 6))
                item.take_snapshot()
                item.save()
            challan.recalculate_totals()
            drafts += 1

        # One cancelled challan (stock was returned).
        customer = active_customers[0]
        challan = SalesChallan(
            customer=customer,
            challan_date=today - timedelta(days=4),
            created_by=sales_user,
            notes="Customer changed their mind after dispatch was prepared.",
        )
        challan.copy_customer_snapshot()
        challan.save()
        for product in random.sample(sellable, 2):
            item = ChallanItem(challan=challan, product=product, quantity=3)
            item.take_snapshot()
            item.save()
        challan.recalculate_totals()
        sales_services.confirm_challan(challan, user=sales_user)
        sales_services.cancel_challan(
            challan, user=users["admin"], reason="Customer cancelled the order before delivery."
        )
        cancelled += 1

        self.stdout.write(f"  + {confirmed} confirmed, {drafts} draft and {cancelled} cancelled challans")

    # -- output ------------------------------------------------------------
    def _print_summary(self):
        self.stdout.write("")
        self.stdout.write(f"  Customers ......... {Customer.objects.count()}")
        self.stdout.write(f"  Follow-ups ........ {FollowUp.objects.count()}")
        self.stdout.write(f"  Products .......... {Product.objects.count()}")
        self.stdout.write(f"  Low stock ......... {Product.objects.low_stock().count()}")
        self.stdout.write(f"  Stock movements ... {StockMovement.objects.count()}")
        self.stdout.write(f"  Challans .......... {SalesChallan.objects.count()}")

    def _print_credentials(self):
        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING("  Test logins (username / password)"))
        for spec in DEMO_USERS:
            self.stdout.write(f"    {spec['role']:<10} {spec['username']:<10} {spec['password']}")
        self.stdout.write("")
