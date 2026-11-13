from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from carts.models import Cart, CartItem
from orders.models import Order, OrderItem
from products.models import Category, Product
from storefront import services
from storefront.management.commands.seed_products import CATEGORIES, PRODUCTS
from storefront.payments import verify_payment_signature

User = get_user_model()


class StorefrontTestMixin:
    @classmethod
    def setUpTestData(cls):
        cls.electronics = Category.objects.create(
            name="Electronics", slug="electronics", icon="💻"
        )
        cls.fashion = Category.objects.create(name="Fashion", slug="fashion", icon="👕")
        cls.headphones = Product.objects.create(
            name="Aurora Wireless Headphones",
            description="Immersive sound with active noise cancellation.",
            category=cls.electronics,
            brand="Aurora",
            price=Decimal("2499.00"),
            mrp=Decimal("3499.00"),
            stock=20,
            is_active=True,
            is_featured=True,
        )
        cls.laptop = Product.objects.create(
            name="Nimbus Pro Laptop",
            description="A lightweight laptop for everyday work.",
            category=cls.electronics,
            brand="Nimbus",
            price=Decimal("74999.00"),
            mrp=Decimal("84999.00"),
            stock=5,
            is_active=True,
        )
        cls.shirt = Product.objects.create(
            name="Everyday Cotton Shirt",
            description="Soft cotton shirt with a relaxed fit.",
            category=cls.fashion,
            brand="Loom",
            price=Decimal("999.00"),
            mrp=Decimal("1499.00"),
            stock=30,
            is_active=True,
            is_featured=True,
        )
        cls.sticker = Product.objects.create(
            name="Laptop Sticker Pack",
            description="A set of six vinyl stickers for your laptop.",
            category=cls.electronics,
            brand="Stickerly",
            price=Decimal("499.00"),
            mrp=Decimal("699.00"),
            stock=50,
            is_active=True,
        )
        cls.sold_out = Product.objects.create(
            name="Sold Out Sneakers",
            description="A limited run that has sold out.",
            category=cls.fashion,
            price=Decimal("1999.00"),
            stock=0,
            is_active=True,
        )
        cls.hidden = Product.objects.create(
            name="Hidden Product",
            description="This should never appear in the storefront.",
            category=cls.electronics,
            price=Decimal("100.00"),
            stock=3,
            is_active=False,
        )

    def add_to_cart(self, product, quantity=1):
        return self.client.post(
            reverse("storefront:cart_add", args=[product.pk]),
            {"quantity": quantity},
        )

    def checkout_payload(self, **overrides):
        payload = {
            "full_name": "Ananya Sharma",
            "email": "ananya@example.com",
            "phone": "9876543210",
            "address": "42, Rose Villa, Indiranagar",
            "city": "Bengaluru",
            "state": "Karnataka",
            "pin_code": "560038",
            "payment_method": "COD",
            "notes": "Please call before delivery",
        }
        payload.update(overrides)
        return payload


class CatalogueTests(StorefrontTestMixin, TestCase):
    def test_seed_catalogue_has_more_than_twenty_products(self):
        self.assertGreaterEqual(len(PRODUCTS), 20)
        self.assertGreaterEqual(len(CATEGORIES), 6)
        self.assertEqual(len({row[0] for row in PRODUCTS}), len(PRODUCTS))

    def test_home_lists_featured_products_and_categories(self):
        response = self.client.get(reverse("storefront:home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Aurora Wireless Headphones")
        self.assertContains(response, "Everyday Cotton Shirt")
        self.assertContains(response, "Electronics")
        self.assertNotContains(response, "Hidden Product")

    def test_product_list_shows_only_active_products(self):
        response = self.client.get(reverse("storefront:product_list"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["result_count"], 5)
        self.assertNotContains(response, "Hidden Product")

    def test_search_matches_name_description_and_brand(self):
        response = self.client.get(reverse("storefront:product_list"), {"q": "noise cancellation"})
        self.assertContains(response, "Aurora Wireless Headphones")
        self.assertNotContains(response, "Everyday Cotton Shirt")

        response = self.client.get(reverse("storefront:product_list"), {"q": "Nimbus"})
        self.assertContains(response, "Nimbus Pro Laptop")
        self.assertNotContains(response, "Aurora Wireless Headphones")

    def test_category_filter(self):
        response = self.client.get(
            reverse("storefront:product_list"), {"category": "fashion"}
        )
        names = [product.name for product in response.context["products"]]
        self.assertIn("Everyday Cotton Shirt", names)
        self.assertIn("Sold Out Sneakers", names)
        self.assertNotIn("Aurora Wireless Headphones", names)
        self.assertNotIn("Nimbus Pro Laptop", names)

    def test_sorting_by_price_low_and_high(self):
        response = self.client.get(reverse("storefront:product_list"), {"sort": "price_low"})
        prices = [product.price for product in response.context["products"]]
        self.assertEqual(prices, sorted(prices))

        response = self.client.get(reverse("storefront:product_list"), {"sort": "price_high"})
        prices = [product.price for product in response.context["products"]]
        self.assertEqual(prices, sorted(prices, reverse=True))

    def test_invalid_sort_falls_back_to_newest(self):
        response = self.client.get(reverse("storefront:product_list"), {"sort": "not-real"})
        self.assertEqual(response.context["sort"], "newest")

    def test_product_detail_and_related_products(self):
        response = self.client.get(
            reverse("storefront:product_detail", args=[self.headphones.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Aurora Wireless Headphones")
        self.assertContains(response, "Buy now")
        self.assertContains(response, "Add to cart")
        related = list(response.context["related_products"])
        self.assertTrue(related)
        self.assertNotIn(self.headphones, related)

    def test_out_of_stock_product_cannot_be_purchased(self):
        response = self.client.get(
            reverse("storefront:product_detail", args=[self.sold_out.pk])
        )
        self.assertContains(response, "Out of stock")
        self.assertNotContains(response, 'formaction="{}"'.format(
            reverse("storefront:buy_now", args=[self.sold_out.pk])
        ))

    def test_hidden_product_detail_is_404(self):
        response = self.client.get(
            reverse("storefront:product_detail", args=[self.hidden.pk])
        )
        self.assertEqual(response.status_code, 404)


class GuestCartTests(StorefrontTestMixin, TestCase):
    def test_add_to_cart_creates_guest_session_cart(self):
        response = self.add_to_cart(self.headphones, 2)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Cart.objects.count(), 1)
        cart = Cart.objects.get()
        self.assertIsNone(cart.user_id)
        self.assertTrue(cart.session_key)
        self.assertEqual(cart.items.get().quantity, 2)

    def test_cart_persists_between_requests(self):
        self.add_to_cart(self.headphones, 1)
        first = self.client.get(reverse("storefront:cart"))
        self.assertContains(first, "Aurora Wireless Headphones")
        second = self.client.get(reverse("storefront:cart"))
        self.assertContains(second, "Aurora Wireless Headphones")
        self.assertEqual(CartItem.objects.count(), 1)

    def test_cart_quantity_is_clamped_to_stock(self):
        self.add_to_cart(self.laptop, 9)
        item = CartItem.objects.get()
        self.assertEqual(item.quantity, self.laptop.stock)

    def test_update_increase_decrease_and_remove(self):
        self.add_to_cart(self.shirt, 1)
        item = CartItem.objects.get()

        self.client.post(
            reverse("storefront:cart_update", args=[item.pk]),
            {"action": "increase"},
        )
        item.refresh_from_db()
        self.assertEqual(item.quantity, 2)

        self.client.post(
            reverse("storefront:cart_update", args=[item.pk]),
            {"action": "decrease"},
        )
        item.refresh_from_db()
        self.assertEqual(item.quantity, 1)

        self.client.post(
            reverse("storefront:cart_update", args=[item.pk]), {"quantity": 4}
        )
        item.refresh_from_db()
        self.assertEqual(item.quantity, 4)

        response = self.client.post(reverse("storefront:cart_remove", args=[item.pk]))
        self.assertRedirects(response, reverse("storefront:cart"))
        self.assertFalse(CartItem.objects.exists())

    def test_cart_totals_include_delivery(self):
        self.add_to_cart(self.sticker, 1)
        response = self.client.get(reverse("storefront:cart"))
        summary = response.context["summary"]
        self.assertEqual(summary.subtotal, Decimal("499.00"))
        self.assertEqual(summary.delivery, Decimal("49.00"))
        self.assertEqual(summary.total, Decimal("548.00"))

    def test_free_delivery_above_threshold(self):
        self.add_to_cart(self.laptop, 1)
        response = self.client.get(reverse("storefront:cart"))
        summary = response.context["summary"]
        self.assertTrue(summary.has_free_delivery)
        self.assertEqual(summary.delivery, Decimal("0.00"))

    def test_clear_cart(self):
        self.add_to_cart(self.shirt, 1)
        response = self.client.post(reverse("storefront:cart_clear"))
        self.assertRedirects(response, reverse("storefront:cart"))
        self.assertEqual(CartItem.objects.count(), 0)

    def test_add_out_of_stock_is_rejected(self):
        response = self.add_to_cart(self.sold_out, 1)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(CartItem.objects.count(), 0)

    def test_cart_page_empty_state(self):
        response = self.client.get(reverse("storefront:cart"))
        self.assertContains(response, "Your cart is empty")


class AuthenticatedCartTests(StorefrontTestMixin, TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="customer@example.com",
            email="customer@example.com",
            password="StrongPass123!",
            first_name="Customer",
        )

    def test_cart_is_saved_to_account_and_survives_logout(self):
        self.client.force_login(self.user)
        self.add_to_cart(self.shirt, 2)
        cart = Cart.objects.get(user=self.user)
        self.assertEqual(cart.items.get().quantity, 2)

        self.client.logout()
        self.client.force_login(self.user)
        cart = Cart.objects.get(user=self.user)
        self.assertEqual(cart.items.get().quantity, 2)

    def test_guest_cart_merges_on_login(self):
        self.add_to_cart(self.shirt, 2)
        guest_cart = Cart.objects.get()
        self.assertIsNone(guest_cart.user_id)
        session_key = guest_cart.session_key

        response = self.client.post(
            reverse("storefront:login"),
            {
                "username": "customer@example.com",
                "password": "StrongPass123!",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Cart.objects.filter(user=self.user).exists())
        user_cart = Cart.objects.get(user=self.user)
        self.assertEqual(user_cart.items.get().quantity, 2)
        self.assertFalse(Cart.objects.filter(session_key=session_key).exists())

    def test_login_page_redirects_authenticated_users(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("storefront:login"))
        self.assertEqual(response.status_code, 302)


class BuyNowTests(StorefrontTestMixin, TestCase):
    def test_buy_now_stores_selection_and_opens_checkout(self):
        response = self.client.post(
            reverse("storefront:buy_now", args=[self.shirt.pk]), {"quantity": 3}
        )
        self.assertRedirects(
            response, f"{reverse('storefront:checkout')}?mode=buy-now"
        )
        data = self.client.session[services.BUY_NOW_SESSION_KEY]
        self.assertEqual(data["product_id"], self.shirt.pk)
        self.assertEqual(data["quantity"], 3)

        checkout = self.client.get(
            reverse("storefront:checkout"), {"mode": "buy-now"}
        )
        self.assertEqual(checkout.status_code, 200)
        self.assertContains(checkout, "Everyday Cotton Shirt")
        self.assertContains(checkout, "Buy Now")

    def test_buy_now_quantity_can_be_increased_and_decreased(self):
        self.client.post(
            reverse("storefront:buy_now", args=[self.shirt.pk]), {"quantity": 2}
        )
        self.client.post(
            reverse("storefront:buy_now_quantity"), {"action": "increase"}
        )
        self.assertEqual(
            self.client.session[services.BUY_NOW_SESSION_KEY]["quantity"], 3
        )
        self.client.post(
            reverse("storefront:buy_now_quantity"), {"action": "decrease"}
        )
        self.assertEqual(
            self.client.session[services.BUY_NOW_SESSION_KEY]["quantity"], 2
        )

    def test_buy_now_quantity_cannot_exceed_stock_or_drop_below_one(self):
        self.client.post(
            reverse("storefront:buy_now", args=[self.laptop.pk]), {"quantity": 5}
        )
        self.client.post(
            reverse("storefront:buy_now_quantity"), {"action": "increase"}
        )
        self.assertEqual(
            self.client.session[services.BUY_NOW_SESSION_KEY]["quantity"],
            self.laptop.stock,
        )
        for _ in range(10):
            self.client.post(
                reverse("storefront:buy_now_quantity"), {"action": "decrease"}
            )
        self.assertEqual(
            self.client.session[services.BUY_NOW_SESSION_KEY]["quantity"], 1
        )

    def test_buy_now_checkout_creates_order_and_clears_selection(self):
        self.client.post(
            reverse("storefront:buy_now", args=[self.shirt.pk]), {"quantity": 2}
        )
        payload = self.checkout_payload()
        payload["mode"] = "buy-now"
        response = self.client.post(reverse("storefront:place_order"), payload)
        self.assertEqual(response.status_code, 302)

        order = Order.objects.get()
        self.assertEqual(order.items.get().quantity, 2)
        self.assertEqual(order.grand_total, Decimal("1998.00"))
        self.assertNotIn(services.BUY_NOW_SESSION_KEY, self.client.session)
        self.shirt.refresh_from_db()
        self.assertEqual(self.shirt.stock, 28)
        self.assertFalse(CartItem.objects.exists())

    def test_buy_now_without_selection_returns_to_catalog(self):
        response = self.client.get(
            reverse("storefront:checkout"), {"mode": "buy-now"}, follow=True
        )
        self.assertRedirects(response, reverse("storefront:product_list"))


class CheckoutTests(StorefrontTestMixin, TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="buyer@example.com",
            email="buyer@example.com",
            password="StrongPass123!",
            first_name="Buyer",
        )

    def test_checkout_requires_items(self):
        response = self.client.get(reverse("storefront:checkout"))
        self.assertRedirects(response, reverse("storefront:cart"))

    def test_checkout_page_renders_all_required_fields(self):
        self.add_to_cart(self.shirt, 1)
        response = self.client.get(reverse("storefront:checkout"))
        self.assertEqual(response.status_code, 200)
        for field in [
            "Full name",
            "Email address",
            "Mobile number",
            "Complete delivery address",
            "PIN code",
            "Cash on Delivery",
        ]:
            self.assertContains(response, field)

    def test_checkout_shows_online_payment_as_ready_but_disabled_without_keys(self):
        self.add_to_cart(self.shirt, 1)
        response = self.client.get(reverse("storefront:checkout"))
        self.assertContains(response, "Razorpay")
        self.assertContains(response, "Not configured")
        self.assertContains(response, "disabled")

    def test_place_cod_order(self):
        self.add_to_cart(self.shirt, 2)
        response = self.client.post(
            reverse("storefront:place_order"), self.checkout_payload()
        )
        self.assertEqual(response.status_code, 302)

        order = Order.objects.get()
        self.assertTrue(order.order_number.startswith("CM-"))
        self.assertEqual(order.status, Order.STATUS_PENDING)
        self.assertEqual(order.payment_method, Order.PAYMENT_COD)
        self.assertEqual(order.payment_status, Order.PAYMENT_STATUS_PENDING)
        self.assertEqual(order.full_name, "Ananya Sharma")
        self.assertEqual(order.phone, "9876543210")
        self.assertEqual(order.zip_code, "560038")
        self.assertEqual(order.subtotal, Decimal("1998.00"))
        self.assertEqual(order.delivery_charge, Decimal("0.00"))
        self.assertEqual(order.grand_total, Decimal("1998.00"))
        self.assertEqual(order.items.get().quantity, 2)
        self.assertEqual(order.total_quantity, 2)

        self.shirt.refresh_from_db()
        self.assertEqual(self.shirt.stock, 28)
        self.assertFalse(CartItem.objects.exists())

        success = self.client.get(
            reverse("storefront:order_success", args=[order.order_number])
        )
        self.assertEqual(success.status_code, 200)
        self.assertContains(success, order.order_number)

    def test_small_order_pays_delivery_fee(self):
        self.add_to_cart(self.sticker, 1)
        self.client.post(reverse("storefront:place_order"), self.checkout_payload())
        order = Order.objects.get()
        self.assertEqual(order.delivery_charge, Decimal("49.00"))
        self.assertEqual(order.grand_total, Decimal("548.00"))

    def test_place_order_requires_valid_details(self):
        self.add_to_cart(self.shirt, 1)
        response = self.client.post(
            reverse("storefront:place_order"),
            self.checkout_payload(
                full_name="",
                phone="123",
                pin_code="12",
                email="not-an-email",
            ),
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Order.objects.count(), 0)
        self.assertContains(response, "Enter a valid", status_code=400)

    def test_online_payment_rejected_when_keys_are_missing(self):
        self.add_to_cart(self.shirt, 1)
        response = self.client.post(
            reverse("storefront:place_order"),
            self.checkout_payload(payment_method="ONLINE"),
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Order.objects.count(), 0)
        self.assertContains(
            response, "Online payment is not enabled yet", status_code=400
        )

    def test_guest_cannot_view_someone_elses_order(self):
        self.add_to_cart(self.shirt, 1)
        self.client.post(reverse("storefront:place_order"), self.checkout_payload())
        order = Order.objects.get()

        other_client = self.client_class()
        response = other_client.get(
            reverse("storefront:order_success", args=[order.order_number])
        )
        self.assertEqual(response.status_code, 404)

    def test_order_history_requires_login_and_only_shows_own_orders(self):
        response = self.client.get(reverse("storefront:order_history"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("storefront:login"), response.url)

        order = Order.objects.create(
            user=self.user,
            full_name="Buyer One",
            email=self.user.email,
            grand_total=Decimal("500.00"),
        )
        other_order = Order.objects.create(
            full_name="Other Person",
            email="other@example.com",
            grand_total=Decimal("900.00"),
        )

        self.client.force_login(self.user)
        response = self.client.get(reverse("storefront:order_history"))
        self.assertContains(response, order.order_number)
        self.assertNotContains(response, other_order.order_number)

        response = self.client.get(
            reverse("storefront:order_detail", args=[other_order.order_number])
        )
        self.assertEqual(response.status_code, 404)

        response = self.client.get(
            reverse("storefront:order_detail", args=[order.order_number])
        )
        self.assertEqual(response.status_code, 200)

    def test_order_numbers_are_unique(self):
        first = Order.objects.create(full_name="A", email="a@example.com")
        second = Order.objects.create(full_name="B", email="b@example.com")
        self.assertNotEqual(first.order_number, second.order_number)

    def test_checkout_prefills_last_delivery_details(self):
        self.client.force_login(self.user)
        Order.objects.create(
            user=self.user,
            full_name="Buyer One",
            email=self.user.email,
            phone="9876543210",
            address="12, Lake Road",
            city="Mysuru",
            state="Karnataka",
            zip_code="570001",
            grand_total=Decimal("500.00"),
        )
        self.add_to_cart(self.shirt, 1)
        response = self.client.get(reverse("storefront:checkout"))
        self.assertContains(response, "12, Lake Road")
        self.assertContains(response, "Mysuru")
        self.assertContains(response, "570001")

    def test_cart_is_cleared_only_after_order_is_created(self):
        self.add_to_cart(self.shirt, 1)
        bad = self.checkout_payload(pin_code="000")
        self.client.post(reverse("storefront:place_order"), bad)
        self.assertTrue(CartItem.objects.exists())
        self.assertEqual(Order.objects.count(), 0)


class PaymentConfigurationTests(TestCase):
    @override_settings(RAZORPAY_ENABLED=False)
    def test_razorpay_disabled_by_default(self):
        from storefront.payments import is_razorpay_enabled

        self.assertFalse(is_razorpay_enabled())

    @override_settings(RAZORPAY_KEY_SECRET="test-secret")
    def test_signature_verification(self):
        import hashlib
        import hmac

        order_id = "order_test123"
        payment_id = "pay_test456"
        signature = hmac.new(
            b"test-secret",
            f"{order_id}|{payment_id}".encode(),
            hashlib.sha256,
        ).hexdigest()
        self.assertTrue(verify_payment_signature(order_id, payment_id, signature))
        self.assertFalse(verify_payment_signature(order_id, payment_id, "bad-signature"))


class DashboardTests(StorefrontTestMixin, TestCase):
    def setUp(self):
        self.staff = User.objects.create_user(
            username="staff@example.com",
            email="staff@example.com",
            password="StrongPass123!",
            first_name="Store",
            last_name="Manager",
            is_staff=True,
        )
        self.customer = User.objects.create_user(
            username="shopper@example.com",
            email="shopper@example.com",
            password="StrongPass123!",
        )

    def test_dashboard_requires_staff(self):
        response = self.client.get(reverse("storefront:dashboard_home"))
        self.assertEqual(response.status_code, 302)

        self.client.force_login(self.customer)
        response = self.client.get(reverse("storefront:dashboard_home"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("storefront:login"), response.url)

    def test_staff_can_view_all_dashboard_pages(self):
        order = Order.objects.create(
            full_name="Ananya Sharma",
            email="ananya@example.com",
            grand_total=Decimal("1048.00"),
        )
        OrderItem.objects.create(
            order=order,
            product=self.shirt,
            quantity=1,
            price=self.shirt.price,
            total_price=self.shirt.price,
        )
        self.client.force_login(self.staff)
        urls = [
            reverse("storefront:dashboard_home"),
            reverse("storefront:dashboard_products"),
            reverse("storefront:dashboard_product_create"),
            reverse("storefront:dashboard_product_edit", args=[self.shirt.pk]),
            reverse("storefront:dashboard_orders"),
            reverse("storefront:dashboard_order_detail", args=[order.order_number]),
            reverse("storefront:dashboard_categories"),
            reverse("storefront:dashboard_category_edit", args=[self.fashion.pk]),
        ]
        for url in urls:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)

    def test_staff_can_create_product(self):
        self.client.force_login(self.staff)
        response = self.client.post(
            reverse("storefront:dashboard_product_create"),
            {
                "name": "Brand New Lamp",
                "category": self.fashion.pk,
                "brand": "Lumen",
                "price": "1299.00",
                "mrp": "1699.00",
                "stock": "12",
                "description": "A warm table lamp for reading corners.",
                "tax_percent": "0",
                "is_active": "on",
                "is_featured": "on",
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        product = Product.objects.get(name="Brand New Lamp")
        self.assertEqual(product.price, Decimal("1299.00"))
        self.assertEqual(product.stock, 12)
        self.assertTrue(product.is_featured)
        self.assertContains(response, "Brand New Lamp")

    def test_staff_can_update_price_and_stock(self):
        self.client.force_login(self.staff)
        response = self.client.post(
            reverse("storefront:dashboard_product_edit", args=[self.shirt.pk]),
            {
                "name": self.shirt.name,
                "category": self.fashion.pk,
                "brand": self.shirt.brand,
                "price": "799.00",
                "mrp": "1299.00",
                "stock": "44",
                "description": self.shirt.description,
                "tax_percent": "0",
                "is_active": "on",
            },
        )
        self.assertRedirects(response, reverse("storefront:dashboard_products"))
        self.shirt.refresh_from_db()
        self.assertEqual(self.shirt.price, Decimal("799.00"))
        self.assertEqual(self.shirt.stock, 44)

    def test_staff_can_toggle_visibility(self):
        self.client.force_login(self.staff)
        self.client.post(
            reverse("storefront:dashboard_product_toggle", args=[self.shirt.pk])
        )
        self.shirt.refresh_from_db()
        self.assertFalse(self.shirt.is_active)

    def test_staff_can_delete_unused_product(self):
        product = Product.objects.create(
            name="Disposable Product",
            price=Decimal("10.00"),
            stock=1,
            is_active=True,
        )
        self.client.force_login(self.staff)
        self.client.post(
            reverse("storefront:dashboard_product_delete", args=[product.pk])
        )
        self.assertFalse(Product.objects.filter(pk=product.pk).exists())

    def test_product_with_order_history_is_archived_instead_of_deleted(self):
        order = Order.objects.create(
            full_name="Ananya Sharma", email="ananya@example.com"
        )
        OrderItem.objects.create(
            order=order,
            product=self.shirt,
            quantity=1,
            price=self.shirt.price,
            total_price=self.shirt.price,
        )
        self.client.force_login(self.staff)
        self.client.post(
            reverse("storefront:dashboard_product_delete", args=[self.shirt.pk])
        )
        self.shirt.refresh_from_db()
        self.assertFalse(self.shirt.is_active)
        self.assertTrue(Product.objects.filter(pk=self.shirt.pk).exists())

    def test_staff_can_update_order_and_payment_status(self):
        order = Order.objects.create(
            full_name="Ananya Sharma",
            email="ananya@example.com",
            grand_total=Decimal("1048.00"),
        )
        self.client.force_login(self.staff)
        response = self.client.post(
            reverse("storefront:dashboard_order_detail", args=[order.order_number]),
            {"status": Order.STATUS_SHIPPED, "payment_status": Order.PAYMENT_STATUS_PAID},
        )
        self.assertRedirects(
            response,
            reverse("storefront:dashboard_order_detail", args=[order.order_number]),
        )
        order.refresh_from_db()
        self.assertEqual(order.status, Order.STATUS_SHIPPED)
        self.assertEqual(order.payment_status, Order.PAYMENT_STATUS_PAID)

        order.status = Order.STATUS_DELIVERED
        order.save()
        self.assertEqual(order.status_index, 3)

    def test_staff_can_create_and_edit_category(self):
        self.client.force_login(self.staff)
        response = self.client.post(
            reverse("storefront:dashboard_categories"),
            {"name": "Kitchen", "icon": "🍳", "description": "Cookware and tools"},
        )
        self.assertRedirects(response, reverse("storefront:dashboard_categories"))
        category = Category.objects.get(name="Kitchen")
        self.assertEqual(category.slug, "kitchen")

        response = self.client.post(
            reverse("storefront:dashboard_category_edit", args=[category.pk]),
            {"name": "Kitchen & Dining", "icon": "🍽️", "description": "Cook and serve"},
        )
        self.assertRedirects(response, reverse("storefront:dashboard_categories"))
        category.refresh_from_db()
        self.assertEqual(category.name, "Kitchen & Dining")

    def test_category_with_products_cannot_be_deleted(self):
        self.client.force_login(self.staff)
        self.client.post(
            reverse("storefront:dashboard_category_delete", args=[self.fashion.pk])
        )
        self.assertTrue(Category.objects.filter(pk=self.fashion.pk).exists())

    def test_empty_category_can_be_deleted(self):
        empty = Category.objects.create(name="Empty", slug="empty")
        self.client.force_login(self.staff)
        self.client.post(
            reverse("storefront:dashboard_category_delete", args=[empty.pk])
        )
        self.assertFalse(Category.objects.filter(pk=empty.pk).exists())


class AccountTests(StorefrontTestMixin, TestCase):
    def test_register_creates_account_and_logs_in(self):
        response = self.client.post(
            reverse("storefront:register"),
            {
                "first_name": "New",
                "last_name": "Customer",
                "email": "new@example.com",
                "phone": "9123456780",
                "password1": "A-very-strong-pass1",
                "password2": "A-very-strong-pass1",
            },
        )
        self.assertEqual(response.status_code, 302)
        user = User.objects.get(email="new@example.com")
        self.assertEqual(user.username, "new@example.com")
        self.assertEqual(user.phone, "9123456780")
        self.assertEqual(int(self.client.session["_auth_user_id"]), user.pk)

    def test_duplicate_email_registration_is_rejected(self):
        User.objects.create_user(
            username="taken@example.com",
            email="taken@example.com",
            password="StrongPass123!",
        )
        response = self.client.post(
            reverse("storefront:register"),
            {
                "first_name": "New",
                "last_name": "Customer",
                "email": "taken@example.com",
                "password1": "A-very-strong-pass1",
                "password2": "A-very-strong-pass1",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "already exists")

    def test_profile_requires_login_and_can_be_updated(self):
        response = self.client.get(reverse("storefront:profile"))
        self.assertEqual(response.status_code, 302)

        user = User.objects.create_user(
            username="profile@example.com",
            email="profile@example.com",
            password="StrongPass123!",
        )
        self.client.force_login(user)
        response = self.client.get(reverse("storefront:profile"))
        self.assertEqual(response.status_code, 200)

        response = self.client.post(
            reverse("storefront:profile"),
            {"first_name": "Updated", "last_name": "Name", "phone": "9988776655"},
        )
        self.assertRedirects(response, reverse("storefront:profile"))
        user.refresh_from_db()
        self.assertEqual(user.first_name, "Updated")
        self.assertEqual(user.phone, "9988776655")
