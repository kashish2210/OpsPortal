from django.contrib import admin

from .models import ChallanItem, ChallanStatus, SalesChallan


class ChallanItemInline(admin.TabularInline):
    model = ChallanItem
    extra = 0
    fields = ("product", "product_sku", "product_name", "quantity", "unit_price", "line_total")
    readonly_fields = ("product_sku", "product_name", "line_total")
    autocomplete_fields = ("product",)


@admin.register(SalesChallan)
class SalesChallanAdmin(admin.ModelAdmin):
    list_display = (
        "challan_number",
        "challan_date",
        "customer_name",
        "status",
        "total_quantity",
        "grand_total",
        "created_by",
    )
    list_filter = ("status", "challan_date")
    search_fields = ("challan_number", "customer_name", "customer_mobile", "vehicle_number")
    date_hierarchy = "challan_date"
    inlines = [ChallanItemInline]
    autocomplete_fields = ("customer",)
    readonly_fields = (
        "challan_number",
        "status",
        "customer_name",
        "customer_business_name",
        "customer_mobile",
        "customer_gst_number",
        "customer_address",
        "total_quantity",
        "total_amount",
        "total_tax",
        "grand_total",
        "created_by",
        "confirmed_by",
        "confirmed_at",
        "cancelled_by",
        "cancelled_at",
        "created_at",
        "updated_at",
    )

    def has_change_permission(self, request, obj=None):
        # Confirmed / cancelled challans are immutable accounting documents.
        if obj is not None and obj.status != ChallanStatus.DRAFT:
            return False
        return super().has_change_permission(request, obj)
