from decimal import Decimal

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.views import LoginView, LogoutView
from django.core.mail import send_mail
from django.db import transaction
from django.db.models import Count, F, Q, Sum
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_GET, require_POST

from carts.models import CartItem
from orders.models import Order, OrderItem
from products.models import Category, Product
from storefront import services
from storefront.forms import (
    CategoryForm,
    CheckoutForm,
    LoginForm,
    ProductForm,
    ProfileForm,
    RegisterForm,
)
from storefront.payments import (
    RazorpayError,
    create_razorpay_order,
    is_razorpay_enabled,
    verify_payment_signature,
)

SORT_OPTIONS = {
    "newest": ("Newest first", "-created_at"),
    "price_low": ("Price: low to high", "price"),
    "price_high": ("Price: high to low", "-price"),
    "name": ("Name: A to Z", "name"),
}

ORDER_ACCESS_SESSION_KEY = "clickmart_order_access"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _staff_check(user):
    return user.is_authenticated and user.is_active and user.is_staff


def staff_required(view_func):
    return user_passes_test(
        _staff_check, login_url=reverse_lazy("storefront:login")
    )(view_func)


def _safe_next(request, fallback):
    next_url = request.POST.get("next") or request.GET.get("next")
    if next_url and url_has_allowed_host_and_scheme(
        next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return next_url
    return fallback


def _categories_with_counts():
    return Category.objects.annotate(
        product_count=Count(
            "products", filter=Q(products__is_active=True), distinct=True
        )
    ).order_by("name")


def _filter_products(request):
    products = Product.objects.filter(is_active=True).select_related("category")

    query = request.GET.get("q", "").strip()
    if query:
        products = products.filter(
            Q(name__icontains=query)
            | Q(description__icontains=query)
            | Q(brand__icontains=query)
            | Q(category__name__icontains=query)
        )

    category_slug = request.GET.get("category", "").strip()
    active_category = None
    if category_slug:
        active_category = Category.objects.filter(slug=category_slug).first()
        if active_category:
            products = products.filter(category=active_category)

    sort = request.GET.get("sort", "newest")
    if sort not in SORT_OPTIONS:
        sort = "newest"
    products = products.order_by(SORT_OPTIONS[sort][1], "-id")

    return {
        "products": products,
        "query": query,
        "active_category": active_category,
        "category_slug": category_slug,
        "sort": sort,
        "sort_options": [
            {"value": key, "label": value[0]} for key, value in SORT_OPTIONS.items()
        ],
        "categories": _categories_with_counts(),
        "result_count": products.count(),
    }


def _related_products(product, limit=4):
    related = list(
        Product.objects.filter(is_active=True, category=product.category)
        .exclude(pk=product.pk)
        .select_related("category")[:limit]
    )
    if len(related) < limit:
        extra = (
            Product.objects.filter(is_active=True)
            .exclude(pk=product.pk)
            .exclude(pk__in=[item.pk for item in related])
            .select_related("category")[: limit - len(related)]
        )
        related.extend(extra)
    return related


def _order_access_allowed(request, order):
    if request.user.is_staff:
        return True
    if request.user.is_authenticated and order.user_id == request.user.id:
        return True
    return order.order_number in request.session.get(ORDER_ACCESS_SESSION_KEY, [])


def _remember_order_access(request, order):
    access = request.session.get(ORDER_ACCESS_SESSION_KEY, [])
    if order.order_number not in access:
        access.append(order.order_number)
        request.session[ORDER_ACCESS_SESSION_KEY] = access[-10:]
        request.session.modified = True


def _send_order_confirmation(order):
    recipient = order.email or getattr(order.user, "email", "")
    if not recipient:
        return
    try:
        send_mail(
            subject=f"Your ClickMart order {order.order_number} is confirmed",
            message=(
                f"Hi {order.full_name or 'there'},\n\n"
                f"Thank you for shopping with ClickMart. We have received your order "
                f"{order.order_number}.\n\n"
                f"Total: Rs. {order.grand_total}\n"
                f"Payment: {order.get_payment_method_display()} "
                f"({order.get_payment_status_display()})\n\n"
                "You can track your order from your ClickMart account.\n\n"
                "Team ClickMart"
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[recipient],
            fail_silently=True,
        )
    except Exception:
        # A mail outage must never lose a successfully placed order.
        pass


# ---------------------------------------------------------------------------
# Storefront
# ---------------------------------------------------------------------------


@require_GET
def home(request):
    products = Product.objects.filter(is_active=True).select_related("category")
    featured = list(products.filter(is_featured=True)[:8])
    if len(featured) < 8:
        fallback = products.exclude(pk__in=[p.pk for p in featured])[: 8 - len(featured)]
        featured.extend(fallback)

    new_arrivals = products.order_by("-created_at")[:4]
    hero_products = featured[:3]

    return render(
        request,
        "storefront/home.html",
        {
            "featured_products": featured,
            "new_arrivals": new_arrivals,
            "hero_products": hero_products,
            "categories": _categories_with_counts(),
            "product_count": products.count(),
        },
    )


@require_GET
def product_list(request):
    context = _filter_products(request)
    return render(request, "storefront/products/list.html", context)


@require_GET
def product_detail(request, pk):
    product = get_object_or_404(
        Product.objects.select_related("category"), pk=pk, is_active=True
    )
    return render(
        request,
        "storefront/products/detail.html",
        {
            "product": product,
            "related_products": _related_products(product),
        },
    )


# ---------------------------------------------------------------------------
# Cart
# ---------------------------------------------------------------------------


@require_GET
def cart_view(request):
    cart = services.get_cart(request)
    items = cart.items.select_related("product").all()
    summary = services.summarize(services.cart_items_for_summary(cart))
    return render(
        request,
        "storefront/cart/detail.html",
        {"cart": cart, "items": items, "summary": summary},
    )


@require_POST
def cart_add(request, product_id):
    product = get_object_or_404(Product, pk=product_id, is_active=True)
    cart = services.get_cart(request)
    try:
        _, message = services.add_to_cart(
            cart, product, request.POST.get("quantity", 1)
        )
        messages.success(request, message)
    except services.CartError as exc:
        messages.error(request, str(exc))

    next_url = request.POST.get("next")
    if next_url == "checkout" and cart.items.exists():
        return redirect("storefront:checkout")
    return redirect(_safe_next(request, reverse("storefront:product_detail", args=[product.pk])))


@require_POST
def cart_update(request, item_id):
    cart = services.get_cart(request)
    try:
        if request.POST.get("action") == "increase":
            item = CartItem.objects.get(pk=item_id, cart=cart)
            services.update_cart_item(cart, item_id, item.quantity + 1)
        elif request.POST.get("action") == "decrease":
            item = CartItem.objects.get(pk=item_id, cart=cart)
            services.update_cart_item(cart, item_id, item.quantity - 1)
        else:
            services.update_cart_item(cart, item_id, request.POST.get("quantity", 1))
        messages.success(request, "Cart updated.")
    except CartItem.DoesNotExist:
        messages.error(request, "That cart item no longer exists.")
    except services.CartError as exc:
        messages.error(request, str(exc))
    return redirect("storefront:cart")


@require_POST
def cart_remove(request, item_id):
    cart = services.get_cart(request)
    try:
        services.remove_cart_item(cart, item_id)
        messages.success(request, "Item removed from your cart.")
    except services.CartError as exc:
        messages.error(request, str(exc))
    return redirect("storefront:cart")


@require_POST
def cart_clear(request):
    cart = services.get_cart(request, create=False)
    if cart:
        cart.items.all().delete()
    messages.success(request, "Your cart is now empty.")
    return redirect("storefront:cart")


# ---------------------------------------------------------------------------
# Buy Now
# ---------------------------------------------------------------------------


@require_POST
def buy_now(request, product_id):
    product = get_object_or_404(Product, pk=product_id, is_active=True)
    try:
        services.set_buy_now(request, product, request.POST.get("quantity", 1))
        return redirect(f"{reverse('storefront:checkout')}?mode=buy-now")
    except services.CartError as exc:
        messages.error(request, str(exc))
        return redirect("storefront:product_detail", pk=product.pk)


@require_POST
def buy_now_quantity(request):
    if not services.get_buy_now(request):
        messages.error(request, "Your Buy Now selection has expired. Please choose a product again.")
        return redirect("storefront:product_list")
    services.update_buy_now_quantity(
        request,
        action=request.POST.get("action"),
        quantity=request.POST.get("quantity"),
    )
    return redirect(f"{reverse('storefront:checkout')}?mode=buy-now")


# ---------------------------------------------------------------------------
# Checkout and orders
# ---------------------------------------------------------------------------


def _checkout_items(request, mode):
    if mode == "buy-now":
        selection = services.get_buy_now(request)
        if not selection:
            return None, None
        product, quantity = selection
        return [(product, quantity)], services.summarize([(product, quantity)])

    cart = services.get_cart(request, create=False)
    if not cart:
        return [], services.summarize([])
    items = services.cart_items_for_summary(cart)
    return items, services.summarize(items)


def _checkout_initial(request):
    user = request.user
    initial = {
        "full_name": "",
        "email": "",
        "phone": "",
        "address": "",
        "city": "",
        "state": "",
        "pin_code": "",
        "payment_method": "COD",
    }
    if user.is_authenticated:
        initial["full_name"] = user.get_full_name().strip() or user.first_name
        initial["email"] = user.email
        initial["phone"] = getattr(user, "phone", "")
        last_order = (
            Order.objects.filter(user=user).exclude(address="").order_by("-created_at").first()
        )
        if last_order:
            initial.update(
                {
                    "full_name": last_order.full_name or initial["full_name"],
                    "email": last_order.email or initial["email"],
                    "phone": last_order.phone or initial["phone"],
                    "address": last_order.address,
                    "city": last_order.city,
                    "state": last_order.state,
                    "pin_code": last_order.zip_code,
                }
            )
    return initial


@require_GET
def checkout(request):
    mode = request.GET.get("mode", "cart")
    if mode not in {"cart", "buy-now"}:
        mode = "cart"

    items, summary = _checkout_items(request, mode)
    if items is None:
        messages.error(request, "Choose a product with Buy Now before checking out.")
        return redirect("storefront:product_list")
    if not items:
        messages.info(request, "Your cart is empty. Add a product to continue.")
        return redirect("storefront:cart")

    return render(
        request,
        "storefront/checkout/checkout.html",
        {
            "form": CheckoutForm(initial=_checkout_initial(request)),
            "items": items,
            "summary": summary,
            "mode": mode,
            "razorpay_enabled": is_razorpay_enabled(),
        },
    )


@require_POST
def place_order(request):
    mode = request.POST.get("mode", "cart")
    if mode not in {"cart", "buy-now"}:
        mode = "cart"

    items, summary = _checkout_items(request, mode)
    if items is None or not items:
        messages.error(request, "Your selection is empty. Please add a product first.")
        return redirect("storefront:cart")

    form = CheckoutForm(request.POST)
    if form.is_valid():
        payment_method = form.cleaned_data["payment_method"]
        if payment_method == Order.PAYMENT_ONLINE and not is_razorpay_enabled():
            form.add_error(
                "payment_method",
                "Online payment is not enabled yet. Please choose Cash on Delivery.",
            )

    if not form.is_valid():
        return render(
            request,
            "storefront/checkout/checkout.html",
            {
                "form": form,
                "items": items,
                "summary": summary,
                "mode": mode,
                "razorpay_enabled": is_razorpay_enabled(),
            },
            status=400,
        )

    try:
        with transaction.atomic():
            # Lock products so two shoppers cannot buy the same last unit.
            locked_items = []
            for product, quantity in items:
                locked = Product.objects.select_for_update().get(pk=product.pk)
                if not locked.is_active:
                    raise services.CartError(
                        f"{locked.name} is no longer available."
                    )
                if locked.stock < quantity:
                    raise services.CartError(
                        f"Only {locked.stock} unit(s) of {locked.name} are left. "
                        "Please update your quantity."
                    )
                locked_items.append((locked, quantity))

            # Recalculate on the server using locked prices.
            summary = services.summarize(locked_items)

            order = Order.objects.create(
                user=request.user if request.user.is_authenticated else None,
                full_name=form.cleaned_data["full_name"],
                email=form.cleaned_data["email"],
                phone=form.cleaned_data["phone"],
                address=form.cleaned_data["address"],
                city=form.cleaned_data["city"],
                state=form.cleaned_data["state"],
                zip_code=form.cleaned_data["pin_code"],
                notes=form.cleaned_data["notes"],
                subtotal=summary.subtotal,
                tax_amount=summary.tax,
                delivery_charge=summary.delivery,
                grand_total=summary.total,
                status=Order.STATUS_PENDING,
                payment_method=form.cleaned_data["payment_method"],
                payment_status=Order.PAYMENT_STATUS_PENDING,
            )

            for product, quantity in locked_items:
                OrderItem.objects.create(
                    order=order,
                    product=product,
                    quantity=quantity,
                    price=product.price,
                    total_price=product.price * quantity,
                )
                Product.objects.filter(pk=product.pk).update(
                    stock=F("stock") - quantity
                )

            if mode == "buy-now":
                services.clear_buy_now(request)
            else:
                cart = services.get_cart(request, create=False)
                if cart:
                    cart.items.all().delete()

            if payment_method == Order.PAYMENT_ONLINE:
                try:
                    razorpay_order = create_razorpay_order(order)
                except RazorpayError as exc:
                    raise services.CartError(str(exc))
                order.razorpay_order_id = razorpay_order.get("id", "")
                order.save(update_fields=["razorpay_order_id"])

        _remember_order_access(request, order)
        transaction.on_commit(lambda: _send_order_confirmation(order))

        if order.payment_method == Order.PAYMENT_ONLINE:
            return redirect("storefront:payment", order_number=order.order_number)
        messages.success(
            request,
            f"Order {order.order_number} placed successfully. "
            "You will pay on delivery.",
        )
        return redirect("storefront:order_success", order_number=order.order_number)

    except services.CartError as exc:
        messages.error(request, str(exc))
        return render(
            request,
            "storefront/checkout/checkout.html",
            {
                "form": form,
                "items": items,
                "summary": summary,
                "mode": mode,
                "razorpay_enabled": is_razorpay_enabled(),
            },
            status=400,
        )


@require_GET
def order_success(request, order_number):
    order = get_object_or_404(
        Order.objects.prefetch_related("items__product"), order_number=order_number
    )
    if not _order_access_allowed(request, order):
        raise Http404
    return render(request, "storefront/orders/success.html", {"order": order})


@login_required
@require_GET
def order_history(request):
    orders = (
        Order.objects.filter(user=request.user)
        .prefetch_related("items__product")
        .order_by("-created_at")
    )
    return render(request, "storefront/orders/history.html", {"orders": orders})


@login_required
@require_GET
def order_detail(request, order_number):
    order = get_object_or_404(
        Order.objects.prefetch_related("items__product"),
        order_number=order_number,
        user=request.user,
    )
    return render(request, "storefront/orders/detail.html", {"order": order})


# ---------------------------------------------------------------------------
# Razorpay payment step (used only when keys are configured)
# ---------------------------------------------------------------------------


@require_GET
def payment_page(request, order_number):
    if not is_razorpay_enabled():
        messages.error(request, "Online payments are not enabled.")
        return redirect("storefront:home")
    order = get_object_or_404(Order, order_number=order_number)
    if not _order_access_allowed(request, order):
        raise Http404
    if order.payment_status == Order.PAYMENT_STATUS_PAID:
        return redirect("storefront:order_success", order_number=order.order_number)
    if not order.razorpay_order_id:
        try:
            razorpay_order = create_razorpay_order(order)
        except RazorpayError as exc:
            messages.error(request, str(exc))
            return redirect(
                "storefront:order_success", order_number=order.order_number
            )
        order.razorpay_order_id = razorpay_order.get("id", "")
        order.save(update_fields=["razorpay_order_id"])
    return render(
        request,
        "storefront/checkout/payment.html",
        {
            "order": order,
            "razorpay_key_id": settings.RAZORPAY_KEY_ID,
        },
    )


@require_POST
def payment_callback(request):
    order = get_object_or_404(
        Order, order_number=request.POST.get("order_number", "")
    )
    if not _order_access_allowed(request, order):
        raise Http404

    valid = verify_payment_signature(
        request.POST.get("razorpay_order_id", ""),
        request.POST.get("razorpay_payment_id", ""),
        request.POST.get("razorpay_signature", ""),
    )
    if valid:
        order.payment_status = Order.PAYMENT_STATUS_PAID
        order.razorpay_payment_id = request.POST.get("razorpay_payment_id", "")
        order.save(update_fields=["payment_status", "razorpay_payment_id"])
        messages.success(request, "Payment received. Your order is confirmed!")
    else:
        order.payment_status = Order.PAYMENT_STATUS_FAILED
        order.save(update_fields=["payment_status"])
        messages.error(
            request,
            "We could not verify the payment. Please contact support with your order number.",
        )
    return redirect("storefront:order_success", order_number=order.order_number)


# ---------------------------------------------------------------------------
# Authentication and account
# ---------------------------------------------------------------------------


class StoreLoginView(LoginView):
    template_name = "storefront/account/login.html"
    authentication_form = LoginForm
    redirect_authenticated_user = True

    def form_valid(self, form):
        response = super().form_valid(form)
        moved = services.merge_session_cart(self.request)
        if moved:
            messages.success(
                self.request,
                "Your guest cart has been merged into your account.",
            )
        else:
            messages.success(self.request, "Welcome back to ClickMart.")
        return response


class StoreLogoutView(LogoutView):
    next_page = reverse_lazy("storefront:home")


def register(request):
    if request.user.is_authenticated:
        return redirect("storefront:home")
    if request.method == "POST":
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user, backend="django.contrib.auth.backends.ModelBackend")
            merged = services.merge_session_cart(request)
            messages.success(
                request,
                "Your account is ready. Happy shopping!"
                + (" Your guest cart is saved." if merged else ""),
            )
            return redirect(_safe_next(request, reverse("storefront:home")))
    else:
        form = RegisterForm()
    return render(request, "storefront/account/register.html", {"form": form})


@login_required
def profile(request):
    if request.method == "POST":
        form = ProfileForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Your profile has been updated.")
            return redirect("storefront:profile")
    else:
        form = ProfileForm(instance=request.user)
    orders = Order.objects.filter(user=request.user)
    return render(
        request,
        "storefront/account/profile.html",
        {
            "form": form,
            "order_count": orders.count(),
            "delivered_count": orders.filter(status=Order.STATUS_DELIVERED).count(),
        },
    )


# ---------------------------------------------------------------------------
# Admin dashboard
# ---------------------------------------------------------------------------


@staff_required
@require_GET
def dashboard_home(request):
    orders = Order.objects.all()
    revenue = orders.exclude(payment_status=Order.PAYMENT_STATUS_FAILED).aggregate(
        total=Sum("grand_total")
    )["total"] or Decimal("0.00")
    context = {
        "product_count": Product.objects.filter(is_active=True).count(),
        "low_stock_count": Product.objects.filter(
            is_active=True, stock__lte=5
        ).count(),
        "order_count": orders.count(),
        "pending_count": orders.filter(status=Order.STATUS_PENDING).count(),
        "delivered_count": orders.filter(status=Order.STATUS_DELIVERED).count(),
        "revenue": revenue,
        "recent_orders": orders.select_related("user")[:8],
        "low_stock_products": Product.objects.filter(
            is_active=True, stock__lte=5
        ).select_related("category")[:6],
    }
    return render(request, "storefront/dashboard/home.html", context)


@staff_required
@require_GET
def dashboard_products(request):
    products = Product.objects.select_related("category").order_by("-created_at")
    query = request.GET.get("q", "").strip()
    if query:
        products = products.filter(
            Q(name__icontains=query)
            | Q(brand__icontains=query)
            | Q(category__name__icontains=query)
        )
    category_slug = request.GET.get("category", "")
    if category_slug:
        products = products.filter(category__slug=category_slug)
    stock_filter = request.GET.get("stock", "")
    if stock_filter == "low":
        products = products.filter(stock__lte=5, stock__gt=0)
    elif stock_filter == "out":
        products = products.filter(stock=0)

    return render(
        request,
        "storefront/dashboard/products.html",
        {
            "products": products,
            "query": query,
            "category_slug": category_slug,
            "stock_filter": stock_filter,
            "categories": Category.objects.all(),
        },
    )


@staff_required
def dashboard_product_create(request):
    if request.method == "POST":
        form = ProductForm(request.POST, request.FILES)
        if form.is_valid():
            product = form.save()
            messages.success(request, f"{product.name} added to the catalog.")
            return redirect("storefront:dashboard_products")
    else:
        form = ProductForm()
    return render(
        request,
        "storefront/dashboard/product_form.html",
        {"form": form, "title": "Add product", "is_create": True},
    )


@staff_required
def dashboard_product_edit(request, pk):
    product = get_object_or_404(Product, pk=pk)
    if request.method == "POST":
        form = ProductForm(request.POST, request.FILES, instance=product)
        if form.is_valid():
            product = form.save()
            messages.success(request, f"{product.name} updated.")
            return redirect("storefront:dashboard_products")
    else:
        form = ProductForm(instance=product)
    return render(
        request,
        "storefront/dashboard/product_form.html",
        {"form": form, "product": product, "title": "Edit product", "is_create": False},
    )


@staff_required
@require_POST
def dashboard_product_delete(request, pk):
    product = get_object_or_404(Product, pk=pk)
    if OrderItem.objects.filter(product=product).exists():
        product.is_active = False
        product.save(update_fields=["is_active"])
        messages.warning(
            request,
            f"{product.name} has order history, so it was archived instead of deleted.",
        )
    else:
        name = product.name
        product.delete()
        messages.success(request, f"{name} was deleted.")
    return redirect("storefront:dashboard_products")


@staff_required
@require_POST
def dashboard_product_toggle(request, pk):
    product = get_object_or_404(Product, pk=pk)
    product.is_active = not product.is_active
    product.save(update_fields=["is_active"])
    messages.success(
        request,
        f"{product.name} is now {'active' if product.is_active else 'hidden'}.",
    )
    return redirect("storefront:dashboard_products")


@staff_required
@require_GET
def dashboard_orders(request):
    orders = Order.objects.select_related("user").prefetch_related("items")
    query = request.GET.get("q", "").strip()
    if query:
        orders = orders.filter(
            Q(order_number__icontains=query)
            | Q(email__icontains=query)
            | Q(full_name__icontains=query)
            | Q(phone__icontains=query)
        )
    status = request.GET.get("status", "")
    if status in dict(Order.STATUS_CHOICES):
        orders = orders.filter(status=status)
    return render(
        request,
        "storefront/dashboard/orders.html",
        {
            "orders": orders,
            "query": query,
            "status": status,
            "status_choices": Order.STATUS_CHOICES,
        },
    )


@staff_required
def dashboard_order_detail(request, order_number):
    order = get_object_or_404(
        Order.objects.prefetch_related("items__product"), order_number=order_number
    )
    if request.method == "POST":
        status = request.POST.get("status")
        payment_status = request.POST.get("payment_status")
        changed = []
        if status in dict(Order.STATUS_CHOICES) and status != order.status:
            order.status = status
            changed.append("status")
        if payment_status in dict(Order.PAYMENT_STATUS_CHOICES) and payment_status != order.payment_status:
            order.payment_status = payment_status
            changed.append("payment_status")
        if changed:
            order.save(update_fields=changed + ["updated_at"])
            messages.success(request, "Order updated.")
        else:
            messages.info(request, "No changes were made.")
        return redirect(
            "storefront:dashboard_order_detail", order_number=order.order_number
        )
    return render(
        request,
        "storefront/dashboard/order_detail.html",
        {
            "order": order,
            "status_choices": Order.STATUS_CHOICES,
            "payment_status_choices": Order.PAYMENT_STATUS_CHOICES,
        },
    )


@staff_required
def dashboard_categories(request):
    form = CategoryForm()
    if request.method == "POST":
        form = CategoryForm(request.POST)
        if form.is_valid():
            category = form.save()
            messages.success(request, f"Category “{category.name}” added.")
            return redirect("storefront:dashboard_categories")
    categories = Category.objects.annotate(
        product_count=Count("products", distinct=True)
    ).order_by("name")
    return render(
        request,
        "storefront/dashboard/categories.html",
        {"form": form, "categories": categories},
    )


@staff_required
def dashboard_category_edit(request, pk):
    category = get_object_or_404(Category, pk=pk)
    if request.method == "POST":
        form = CategoryForm(request.POST, instance=category)
        if form.is_valid():
            form.save()
            messages.success(request, "Category updated.")
            return redirect("storefront:dashboard_categories")
    else:
        form = CategoryForm(instance=category)
    return render(
        request,
        "storefront/dashboard/category_form.html",
        {"form": form, "category": category},
    )


@staff_required
@require_POST
def dashboard_category_delete(request, pk):
    category = get_object_or_404(Category, pk=pk)
    if category.products.exists():
        messages.error(
            request,
            "Move or delete the products in this category before deleting it.",
        )
    else:
        name = category.name
        category.delete()
        messages.success(request, f"Category “{name}” deleted.")
    return redirect("storefront:dashboard_categories")
