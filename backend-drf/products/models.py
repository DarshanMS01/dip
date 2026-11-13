from decimal import Decimal

from django.db import models
from django.utils.text import slugify


class Category(models.Model):
    """A storefront category used for filtering products."""

    name = models.CharField(max_length=80, unique=True)
    slug = models.SlugField(max_length=90, unique=True, blank=True)
    description = models.CharField(max_length=240, blank=True)
    icon = models.CharField(
        max_length=8,
        blank=True,
        default="🛍️",
        help_text="A short emoji shown on category cards.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "categories"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Product(models.Model):
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to="products/", blank=True, null=True)
    price = models.DecimalField(max_digits=12, decimal_places=2)  # 200.00
    mrp = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        blank=True,
        null=True,
        help_text="Optional original price shown as a strike-through.",
    )
    stock = models.PositiveIntegerField()
    tax_percent = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal("0.00")
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="products",
    )
    brand = models.CharField(max_length=100, blank=True)
    is_active = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.name

    @property
    def in_stock(self):
        return self.stock > 0

    @property
    def stock_label(self):
        if self.stock <= 0:
            return "Out of stock"
        if self.stock <= 5:
            return f"Only {self.stock} left"
        return "In stock"

    @property
    def discount_percent(self):
        if self.mrp and self.mrp > self.price:
            return int(((self.mrp - self.price) / self.mrp) * 100)
        return 0

    @property
    def savings(self):
        if self.mrp and self.mrp > self.price:
            return self.mrp - self.price
        return 0
