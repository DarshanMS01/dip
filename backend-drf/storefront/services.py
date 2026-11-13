"""Shared storefront logic for carts, Buy Now and order totals.

Keeping this in one place means the product pages, cart, checkout and order
placement all calculate quantities and prices exactly the same way.
"""

import secrets
from dataclasses import dataclass
from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.db.models import Sum

from carts.models import Cart, CartItem
from products.models import Product

CART_SESSION_KEY = "clickmart_cart_key"
BUY_NOW_SESSION_KEY = "clickmart_buy_now"


class CartError(Exception):
    """Raised when a cart action cannot be completed (stock, quantity, etc.)."""


@dataclass
class OrderSummary:
    subtotal: Decimal
    tax: Decimal
    delivery: Decimal
    total: Decimal

    @property
    def free_delivery_remaining(self):
        threshold = Decimal(str(settings.STORE_FREE_DELIVERY_THRESHOLD))
        return max(threshold - self.subtotal, Decimal("0.00"))

    @property
    def has_free_delivery(self):
        return self.delivery == 0

    @property
    def free_delivery_progress(self):
        threshold = Decimal(str(settings.STORE_FREE_DELIVERY_THRESHOLD))
        if threshold <= 0 or self.subtotal >= threshold:
            return 100
        return int((self.subtotal / threshold) * 100)


def _money(value):
    return Decimal(str(value)).quantize(Decimal("0.01"))


def _session_cart_key(request):
    key = request.session.get(CART_SESSION_KEY)
    if not key:
        key = secrets.token_urlsafe(24)[:40]
        request.session[CART_SESSION_KEY] = key
        request.session.modified = True
    return key


def get_session_cart(request, create=True):
    key = request.session.get(CART_SESSION_KEY)
    if not key:
        if not create:
            return None
        key = _session_cart_key(request)
    cart = (
        Cart.objects.filter(session_key=key, user__isnull=True)
        .prefetch_related("items__product")
        .first()
    )
    if cart:
        return cart
    if not create:
        return None
    return Cart.objects.create(session_key=key)


def get_cart(request, create=True):
    """Return the signed-in customer's cart, or a session cart for guests."""
    if request.user.is_authenticated:
        cart, _ = Cart.objects.get_or_create(user=request.user)
        return cart
    return get_session_cart(request, create=create)


def get_cart_count(request):
    cart = get_cart(request, create=False)
    if not cart:
        return 0
    return (
        CartItem.objects.filter(cart=cart).aggregate(total=Sum("quantity"))["total"]
        or 0
    )


def _coerce_quantity(quantity):
    try:
        quantity = int(quantity)
    except (TypeError, ValueError):
        raise CartError("Please enter a valid quantity.")
    if quantity < 1:
        raise CartError("Quantity must be at least 1.")
    return quantity


def add_to_cart(cart, product, quantity=1):
    """Add a product and return (item, message). Quantities are stock-clamped."""
    quantity = _coerce_quantity(quantity)
    if not product.is_active:
        raise CartError("This product is no longer available.")
    if product.stock < 1:
        raise CartError(f"{product.name} is out of stock.")

    item = CartItem.objects.filter(cart=cart, product=product).first()
    current = item.quantity if item else 0
    desired = current + quantity

    if desired > product.stock:
        if current >= product.stock:
            raise CartError(
                f"You already have the maximum available quantity of {product.name}."
            )
        desired = product.stock
        message = (
            f"Only {product.stock} unit(s) of {product.name} are available, "
            "so we updated your cart to the maximum."
        )
    else:
        message = f"{product.name} added to your cart."

    if item:
        item.quantity = desired
        item.save(update_fields=["quantity"])
    else:
        item = CartItem.objects.create(
            cart=cart, product=product, quantity=desired
        )
    return item, message


def update_cart_item(cart, item_id, quantity):
    """Set an item's quantity. A quantity of 0 removes it."""
    try:
        quantity = int(quantity)
    except (TypeError, ValueError):
        raise CartError("Please enter a valid quantity.")
    if quantity < 0:
        raise CartError("Quantity cannot be negative.")

    try:
        item = CartItem.objects.select_related("product").get(
            pk=item_id, cart=cart
        )
    except CartItem.DoesNotExist:
        raise CartError("That cart item no longer exists.")

    if quantity == 0:
        item.delete()
        return None
    if quantity > item.product.stock:
        raise CartError(
            f"Only {item.product.stock} unit(s) of {item.product.name} are available."
        )
    item.quantity = quantity
    item.save(update_fields=["quantity"])
    return item


def remove_cart_item(cart, item_id):
    deleted, _ = CartItem.objects.filter(pk=item_id, cart=cart).delete()
    if not deleted:
        raise CartError("That cart item no longer exists.")


def summarize(items):
    """Calculate totals from an iterable of (product, quantity) pairs."""
    subtotal = Decimal("0.00")
    tax = Decimal("0.00")
    count = 0
    for product, quantity in items:
        line = product.price * quantity
        subtotal += line
        tax += line * product.tax_percent / Decimal("100")
        count += quantity

    if count == 0:
        delivery = Decimal("0.00")
    else:
        threshold = Decimal(str(settings.STORE_FREE_DELIVERY_THRESHOLD))
        delivery = (
            Decimal("0.00")
            if subtotal >= threshold
            else Decimal(str(settings.STORE_DELIVERY_FEE))
        )

    return OrderSummary(
        subtotal=_money(subtotal),
        tax=_money(tax),
        delivery=_money(delivery),
        total=_money(subtotal + tax + delivery),
    )


def cart_items_for_summary(cart):
    return [(item.product, item.quantity) for item in cart.items.select_related("product")]


# ---------------------------------------------------------------------------
# Buy Now
# ---------------------------------------------------------------------------


def set_buy_now(request, product, quantity=1):
    quantity = _coerce_quantity(quantity)
    if not product.is_active or product.stock < 1:
        raise CartError(f"{product.name} is out of stock.")
    quantity = min(quantity, product.stock)
    request.session[BUY_NOW_SESSION_KEY] = {
        "product_id": product.pk,
        "quantity": quantity,
    }
    request.session.modified = True
    return quantity


def get_buy_now(request):
    """Return (product, quantity) for the active Buy Now selection, if any."""
    data = request.session.get(BUY_NOW_SESSION_KEY)
    if not isinstance(data, dict) or not data.get("product_id"):
        return None
    product = Product.objects.filter(
        pk=data.get("product_id"), is_active=True
    ).first()
    if not product:
        clear_buy_now(request)
        return None
    quantity = data.get("quantity", 1)
    try:
        quantity = int(quantity)
    except (TypeError, ValueError):
        quantity = 1
    if product.stock < 1:
        quantity = 1
    else:
        quantity = max(1, min(quantity, product.stock))
    return product, quantity


def update_buy_now_quantity(request, action=None, quantity=None):
    current = get_buy_now(request)
    if not current:
        return None
    product, current_qty = current

    if action == "increase":
        new_qty = current_qty + 1
    elif action == "decrease":
        new_qty = current_qty - 1
    else:
        new_qty = _coerce_quantity(quantity or current_qty)

    new_qty = max(1, min(new_qty, max(product.stock, 1)))
    request.session[BUY_NOW_SESSION_KEY] = {
        "product_id": product.pk,
        "quantity": new_qty,
    }
    request.session.modified = True
    return product, new_qty


def clear_buy_now(request):
    if BUY_NOW_SESSION_KEY in request.session:
        del request.session[BUY_NOW_SESSION_KEY]
        request.session.modified = True


# ---------------------------------------------------------------------------
# Cart merge after login
# ---------------------------------------------------------------------------


@transaction.atomic
def merge_session_cart(request):
    """Move a guest's session cart into their account cart after login."""
    if not request.user.is_authenticated:
        return 0
    key = request.session.get(CART_SESSION_KEY)
    if not key:
        return 0

    guest_cart = (
        Cart.objects.filter(session_key=key, user__isnull=True)
        .prefetch_related("items__product")
        .first()
    )
    if not guest_cart:
        return 0

    user_cart, _ = Cart.objects.get_or_create(user=request.user)
    moved = 0
    for item in guest_cart.items.all():
        existing = CartItem.objects.filter(
            cart=user_cart, product=item.product
        ).first()
        if existing:
            existing.quantity = min(
                existing.quantity + item.quantity, item.product.stock
            )
            existing.save(update_fields=["quantity"])
        else:
            item.cart = user_cart
            item.save(update_fields=["cart"])
        moved += item.quantity

    guest_cart.delete()
    request.session.pop(CART_SESSION_KEY, None)
    request.session.modified = True
    return moved
