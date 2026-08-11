from django.contrib import admin

from .models import Product, StockMovement


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = (
        "sku",
        "name",
        "category",
        "unit_price",
        "current_stock",
        "min_stock_alert",
        "location",
        "is_active",
    )
    list_filter = ("is_active", "category", "location", "unit")
    search_fields = ("sku", "name", "category", "hsn_code", "location")
    readonly_fields = ("current_stock", "created_at", "updated_at", "created_by", "updated_by")
    fieldsets = (
        (None, {"fields": ("name", "sku", "category", "description", "is_active")}),
        ("Pricing", {"fields": ("unit", "unit_price", "hsn_code", "tax_rate")}),
        ("Stock", {"fields": ("current_stock", "min_stock_alert", "location")}),
        ("Image", {"fields": ("image",)}),
        ("Audit", {"fields": ("created_by", "updated_by", "created_at", "updated_at")}),
    )


@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = (
        "created_at",
        "product",
        "movement_type",
        "quantity",
        "reason",
        "reference",
        "balance_after",
        "created_by",
    )
    list_filter = ("movement_type", "reason", "created_at")
    search_fields = ("product__sku", "product__name", "reference", "notes")
    autocomplete_fields = ("product",)
    date_hierarchy = "created_at"

    def has_change_permission(self, request, obj=None):
        # The ledger is append-only.
        return False

    def has_delete_permission(self, request, obj=None):
        return False
