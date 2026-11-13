from decimal import Decimal

from django.conf import settings
from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from products.models import Product

User = get_user_model()


class Cart(models.Model):
    """A cart belongs either to a signed-in customer or to an anonymous session."""

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="cart",
    )
    session_key = models.CharField(max_length=40, blank=True, null=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        owner = self.user.email if self.user_id else f"session:{self.session_key}"
        return f"Cart({owner})"

    @property
    def total_quantity(self):
        return sum(item.quantity for item in self.items.all())

    @property
    def subtotal(self):
        subtotal = sum(
            (item.product.price * item.quantity for item in self.items.all()),
            start=Decimal("0.00"),
        )
        return subtotal

    @property
    def tax_amount(self):
        tax = sum(
            (
                item.product.price
                * item.quantity
                * item.product.tax_percent
                / 100
                for item in self.items.all()
            ),
            start=0,
        )
        return tax

    @property
    def delivery_charge(self):
        """Free delivery above the configured threshold, flat fee otherwise."""
        if not self.items.exists():
            return 0

        if self.subtotal >= Decimal(str(settings.STORE_FREE_DELIVERY_THRESHOLD)):
            return 0
        return Decimal(str(settings.STORE_DELIVERY_FEE))

    @property
    def grand_total(self):
        return self.subtotal + self.tax_amount + self.delivery_charge


class CartItem(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    added_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["added_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["cart", "product"], name="unique_cart_product"
            )
        ]

    def __str__(self):
        return f"{self.product.name} x {self.quantity}"

    @property
    def total_price(self):
        return self.product.price * self.quantity
