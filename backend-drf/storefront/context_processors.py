from storefront.services import get_cart_count


def cart_summary(request):
    """Make the cart count and store branding available to every template."""
    from django.conf import settings

    return {
        "cart_item_count": get_cart_count(request),
        "store_name": settings.STORE_NAME,
        "free_delivery_threshold": settings.STORE_FREE_DELIVERY_THRESHOLD,
        "delivery_fee": settings.STORE_DELIVERY_FEE,
        "razorpay_enabled": settings.RAZORPAY_ENABLED,
    }
