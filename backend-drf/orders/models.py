import secrets
from decimal import Decimal

from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from products.models import Product

User = get_user_model()


class Order(models.Model):
    STATUS_PENDING = "PENDING"
    STATUS_CONFIRMED = "CONFIRMED"
    STATUS_SHIPPED = "SHIPPED"
    STATUS_DELIVERED = "DELIVERED"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_CONFIRMED, "Confirmed"),
        (STATUS_SHIPPED, "Shipped"),
        (STATUS_DELIVERED, "Delivered"),
    ]

    PAYMENT_COD = "COD"
    PAYMENT_ONLINE = "ONLINE"
    PAYMENT_CHOICES = [
        (PAYMENT_COD, "Cash on Delivery"),
        (PAYMENT_ONLINE, "Online Payment (Razorpay)"),
    ]

    PAYMENT_STATUS_PENDING = "PENDING"
    PAYMENT_STATUS_PAID = "PAID"
    PAYMENT_STATUS_FAILED = "FAILED"
    PAYMENT_STATUS_CHOICES = [
        (PAYMENT_STATUS_PENDING, "Pending"),
        (PAYMENT_STATUS_PAID, "Paid"),
        (PAYMENT_STATUS_FAILED, "Failed"),
    ]

    order_number = models.CharField(
        max_length=24, unique=True, blank=True, null=True, editable=False
    )
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="orders",
    )
    full_name = models.CharField(max_length=150, blank=True, default="")
    email = models.EmailField(blank=True, default="")
    phone = models.CharField(max_length=15, blank=True, default="")
    address = models.CharField(max_length=500, blank=True, default="")
    city = models.CharField(max_length=80, blank=True, default="")
    state = models.CharField(max_length=80, blank=True, default="")
    zip_code = models.CharField(max_length=10, blank=True, default="")
    notes = models.CharField(max_length=300, blank=True, default="")

    subtotal = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00")
    )
    tax_amount = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00")
    )
    delivery_charge = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00")
    )
    grand_total = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00")
    )

    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING
    )
    payment_method = models.CharField(
        max_length=10, choices=PAYMENT_CHOICES, default=PAYMENT_COD
    )
    payment_status = models.CharField(
        max_length=10,
        choices=PAYMENT_STATUS_CHOICES,
        default=PAYMENT_STATUS_PENDING,
    )

    # Razorpay-ready fields. They stay empty until online payments are enabled.
    razorpay_order_id = models.CharField(max_length=100, blank=True)
    razorpay_payment_id = models.CharField(max_length=100, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.order_number or f'Order #{self.pk}'} - {self.email or 'guest'}"

    def save(self, *args, **kwargs):
        if not self.order_number:
            self.order_number = self._generate_order_number()
        super().save(*args, **kwargs)

    @classmethod
    def _generate_order_number(cls):
        prefix = f"CM-{timezone.now():%y%m%d}"
        while True:
            candidate = f"{prefix}-{secrets.token_hex(3).upper()}"
            if not cls.objects.filter(order_number=candidate).exists():
                return candidate

    @property
    def total_quantity(self):
        return sum(item.quantity for item in self.items.all())

    @property
    def status_index(self):
        order = [
            self.STATUS_PENDING,
            self.STATUS_CONFIRMED,
            self.STATUS_SHIPPED,
            self.STATUS_DELIVERED,
        ]
        try:
            return order.index(self.status)
        except ValueError:
            return 0


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField()
    price = models.DecimalField(max_digits=12, decimal_places=2)
    total_price = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return f"{self.product.name} - {self.quantity}"
