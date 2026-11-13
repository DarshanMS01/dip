from django.conf import settings
from django.core.mail import send_mail


def send_order_notification(order):
    """Send an order confirmation for both account and guest checkout orders."""
    recipient = order.email or getattr(order.user, "email", "")
    if not recipient:
        return False

    customer_name = order.full_name or getattr(order.user, "first_name", "") or "there"
    send_mail(
        subject=f"Order {order.order_number} is received",
        message=(
            f"Hi {customer_name},\n\n"
            f"Your order {order.order_number} has been placed successfully.\n\n"
            f"Items: {order.total_quantity}\n"
            f"Total: Rs. {order.grand_total}\n"
            f"Payment: {order.get_payment_method_display()} "
            f"({order.get_payment_status_display()})\n\n"
            "Thank you for shopping with us.\n"
            "Team ClickMart"
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[recipient],
        fail_silently=True,
    )
    return True
