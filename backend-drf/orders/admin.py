from django.contrib import admin

from .models import Order, OrderItem


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ("product", "quantity", "price", "total_price")
    can_delete = False


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        "order_number",
        "full_name",
        "email",
        "grand_total",
        "status",
        "payment_method",
        "payment_status",
        "created_at",
    )
    list_filter = ("status", "payment_method", "payment_status", "created_at")
    search_fields = ("order_number", "full_name", "email", "phone")
    readonly_fields = (
        "order_number",
        "subtotal",
        "tax_amount",
        "delivery_charge",
        "grand_total",
        "razorpay_order_id",
        "razorpay_payment_id",
        "created_at",
        "updated_at",
    )
    inlines = [OrderItemInline]
    date_hierarchy = "created_at"
    fieldsets = (
        ("Order", {"fields": ("order_number", "user", "status", "created_at", "updated_at")}),
        ("Customer", {"fields": ("full_name", "email", "phone")}),
        ("Delivery", {"fields": ("address", "city", "state", "zip_code", "notes")}),
        (
            "Totals",
            {"fields": ("subtotal", "tax_amount", "delivery_charge", "grand_total")},
        ),
        (
            "Payment",
            {
                "fields": (
                    "payment_method",
                    "payment_status",
                    "razorpay_order_id",
                    "razorpay_payment_id",
                )
            },
        ),
    )
