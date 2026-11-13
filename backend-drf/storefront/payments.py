"""Razorpay integration scaffolding.

Set RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET in the environment (or .env) to
enable online payments. The checkout page automatically unlocks the online
payment option when both keys are present.
"""

import base64
import hashlib
import hmac
import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.conf import settings


class RazorpayError(Exception):
    pass


def is_razorpay_enabled():
    return bool(getattr(settings, "RAZORPAY_ENABLED", False))


def create_razorpay_order(order):
    """Create a Razorpay order for an existing Django order.

    Returns the Razorpay order dictionary, including its ``id``.
    """
    if not is_razorpay_enabled():
        raise RazorpayError("Razorpay keys are not configured.")

    payload = json.dumps(
        {
            "amount": int(order.grand_total * 100),  # Razorpay expects paise
            "currency": "INR",
            "receipt": order.order_number,
            "notes": {
                "order_number": order.order_number,
                "customer_email": order.email,
            },
        }
    ).encode("utf-8")

    credentials = base64.b64encode(
        f"{settings.RAZORPAY_KEY_ID}:{settings.RAZORPAY_KEY_SECRET}".encode()
    ).decode()

    request = Request(
        "https://api.razorpay.com/v1/orders",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Basic {credentials}",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=15) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RazorpayError(f"Razorpay rejected the order: {detail}") from exc
    except (URLError, TimeoutError) as exc:
        raise RazorpayError("Could not reach Razorpay. Please try again.") from exc


def verify_payment_signature(razorpay_order_id, razorpay_payment_id, signature):
    """Verify the signature sent back by Razorpay Checkout."""
    if not all([razorpay_order_id, razorpay_payment_id, signature]):
        return False
    expected = hmac.new(
        settings.RAZORPAY_KEY_SECRET.encode(),
        f"{razorpay_order_id}|{razorpay_payment_id}".encode(),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature)
