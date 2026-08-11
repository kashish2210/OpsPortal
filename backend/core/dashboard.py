"""Dashboard aggregation endpoint.

One round-trip that gives the SPA everything the landing screen shows: KPI
tiles, low-stock warnings, follow-ups that are due and the latest activity.
"""

from datetime import timedelta
from decimal import Decimal

from django.db.models import Count, DecimalField, F, Sum
from django.db.models.functions import Coalesce, TruncDate
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from crm.models import Customer, CustomerStatus, FollowUp
from crm.serializers import CustomerListSerializer, FollowUpSerializer
from inventory.models import Product, StockMovement
from inventory.serializers import ProductListSerializer, StockMovementSerializer
from sales.models import ChallanStatus, SalesChallan
from sales.serializers import SalesChallanListSerializer

MONEY = DecimalField(max_digits=18, decimal_places=2)


@extend_schema(
    tags=["Dashboard"],
    summary="Dashboard summary",
    description=(
        "KPI counters plus the five most relevant rows for each module. "
        "Available to every authenticated role."
    ),
)
class DashboardAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        today = timezone.localdate()
        month_start = today.replace(day=1)

        customers = Customer.objects.all()
        products = Product.objects.all()
        challans = SalesChallan.objects.all()
        confirmed = challans.filter(status=ChallanStatus.CONFIRMED)

        stock_totals = products.filter(is_active=True).aggregate(
            units=Coalesce(Sum("current_stock"), 0),
            value=Coalesce(
                Sum(F("current_stock") * F("unit_price"), output_field=MONEY),
                Decimal("0.00"),
                output_field=MONEY,
            ),
        )

        follow_ups_due_qs = (
            customers.filter(follow_up_date__isnull=False, follow_up_date__lte=today)
            .exclude(status=CustomerStatus.INACTIVE)
            .order_by("follow_up_date")
        )
        low_stock_qs = products.low_stock().order_by("current_stock", "name")

        payload = {
            "generated_at": timezone.now(),
            "user": {
                "id": request.user.id,
                "name": request.user.display_name,
                "role": request.user.role,
                "role_display": request.user.get_role_display(),
            },
            "customers": {
                "total": customers.count(),
                "leads": customers.filter(status=CustomerStatus.LEAD).count(),
                "active": customers.filter(status=CustomerStatus.ACTIVE).count(),
                "inactive": customers.filter(status=CustomerStatus.INACTIVE).count(),
                "follow_ups_due": follow_ups_due_qs.count(),
                "added_this_month": customers.filter(created_at__date__gte=month_start).count(),
            },
            "inventory": {
                "total_products": products.count(),
                "active_products": products.filter(is_active=True).count(),
                "low_stock": low_stock_qs.count(),
                "out_of_stock": products.out_of_stock().count(),
                "total_stock_units": stock_totals["units"],
                "stock_value": stock_totals["value"],
            },
            "sales": {
                "total_challans": challans.count(),
                "draft": challans.filter(status=ChallanStatus.DRAFT).count(),
                "confirmed": confirmed.count(),
                "cancelled": challans.filter(status=ChallanStatus.CANCELLED).count(),
                "units_shipped": confirmed.aggregate(t=Coalesce(Sum("total_quantity"), 0))["t"],
                "confirmed_value": confirmed.aggregate(
                    t=Coalesce(Sum("grand_total"), Decimal("0.00"), output_field=MONEY)
                )["t"],
                "this_month_value": confirmed.filter(challan_date__gte=month_start).aggregate(
                    t=Coalesce(Sum("grand_total"), Decimal("0.00"), output_field=MONEY)
                )["t"],
            },
            "recent_challans": SalesChallanListSerializer(
                challans.select_related("created_by").annotate(item_count=Count("items"))[:5],
                many=True,
            ).data,
            "low_stock_products": ProductListSerializer(low_stock_qs[:5], many=True).data,
            "follow_ups_due": CustomerListSerializer(follow_ups_due_qs[:5], many=True).data,
            "recent_movements": StockMovementSerializer(
                StockMovement.objects.select_related("product", "created_by")[:8], many=True
            ).data,
            "recent_follow_ups": FollowUpSerializer(
                FollowUp.objects.select_related("customer", "created_by")[:5], many=True
            ).data,
            "sales_trend": self._sales_trend(confirmed),
        }
        return Response(payload)

    @staticmethod
    def _sales_trend(confirmed_qs, days=14):
        """Confirmed challan value per day for the last fortnight."""
        since = timezone.localdate() - timedelta(days=days - 1)
        rows = (
            confirmed_qs.filter(challan_date__gte=since)
            .annotate(day=TruncDate("challan_date"))
            .values("day")
            .annotate(
                value=Coalesce(Sum("grand_total"), Decimal("0.00"), output_field=MONEY),
                count=Count("id"),
            )
            .order_by("day")
        )
        by_day = {row["day"]: row for row in rows}
        trend = []
        for offset in range(days):
            day = since + timedelta(days=offset)
            row = by_day.get(day)
            trend.append(
                {
                    "date": day.isoformat(),
                    "value": str(row["value"]) if row else "0.00",
                    "count": row["count"] if row else 0,
                }
            )
        return trend
