from django.contrib import admin
from django.utils.html import format_html

from .models import Category, Product


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "icon", "product_count")
    search_fields = ("name",)
    prepopulated_fields = {"slug": ("name",)}

    @admin.display(description="Products")
    def product_count(self, category):
        return category.products.count()


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "category",
        "brand",
        "price",
        "stock",
        "is_active",
        "is_featured",
        "preview",
    )
    list_filter = ("is_active", "is_featured", "category", "brand")
    search_fields = ("name", "description", "brand", "category__name")
    list_editable = ("price", "stock", "is_active", "is_featured")
    ordering = ("-created_at",)
    readonly_fields = ("created_at", "updated_at", "preview")
    fieldsets = (
        (None, {"fields": ("name", "category", "brand", "description")}),
        ("Pricing & stock", {"fields": ("price", "mrp", "tax_percent", "stock")}),
        ("Media", {"fields": ("image", "preview")}),
        ("Visibility", {"fields": ("is_active", "is_featured")}),
        ("Timestamps", {"fields": ("created_at", "updated_at")}),
    )

    @admin.display(description="Image")
    def preview(self, product):
        if not product.image:
            return "—"
        return format_html(
            '<img src="{}" alt="{}" style="height:54px;width:54px;object-fit:cover;border-radius:6px;" />',
            product.image.url,
            product.name,
        )
