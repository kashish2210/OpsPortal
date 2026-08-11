from django.contrib import admin

from .models import Customer, FollowUp


class FollowUpInline(admin.TabularInline):
    model = FollowUp
    extra = 0
    fields = ("channel", "note", "next_follow_up_date", "created_by", "created_at")
    readonly_fields = ("created_at",)


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "name",
        "business_name",
        "mobile",
        "customer_type",
        "status",
        "city",
        "follow_up_date",
    )
    list_filter = ("status", "customer_type", "city", "created_at")
    search_fields = ("code", "name", "business_name", "mobile", "email", "gst_number")
    readonly_fields = ("code", "created_at", "updated_at", "created_by", "updated_by")
    inlines = [FollowUpInline]
    date_hierarchy = "created_at"
    fieldsets = (
        (None, {"fields": ("code", "name", "business_name", "customer_type", "status")}),
        ("Contact", {"fields": ("mobile", "email", "gst_number")}),
        ("Address", {"fields": ("address", "city", "state", "pincode")}),
        ("CRM", {"fields": ("follow_up_date", "credit_limit", "notes")}),
        ("Audit", {"fields": ("created_by", "updated_by", "created_at", "updated_at")}),
    )


@admin.register(FollowUp)
class FollowUpAdmin(admin.ModelAdmin):
    list_display = ("customer", "channel", "next_follow_up_date", "created_by", "created_at")
    list_filter = ("channel", "created_at")
    search_fields = ("customer__name", "customer__mobile", "note")
    autocomplete_fields = ("customer",)
