from django.urls import path

from storefront import views

app_name = "storefront"

urlpatterns = [
    # Storefront
    path("", views.home, name="home"),
    path("products/", views.product_list, name="product_list"),
    path("products/<int:pk>/", views.product_detail, name="product_detail"),

    # Cart
    path("cart/", views.cart_view, name="cart"),
    path("cart/add/<int:product_id>/", views.cart_add, name="cart_add"),
    path("cart/item/<int:item_id>/update/", views.cart_update, name="cart_update"),
    path("cart/item/<int:item_id>/remove/", views.cart_remove, name="cart_remove"),
    path("cart/clear/", views.cart_clear, name="cart_clear"),

    # Buy Now
    path("buy-now/<int:product_id>/", views.buy_now, name="buy_now"),
    path("buy-now/quantity/", views.buy_now_quantity, name="buy_now_quantity"),

    # Checkout and orders
    path("checkout/", views.checkout, name="checkout"),
    path("checkout/place-order/", views.place_order, name="place_order"),
    path(
        "order/<str:order_number>/success/",
        views.order_success,
        name="order_success",
    ),

    # Payment (Razorpay-ready)
    path(
        "payment/<str:order_number>/",
        views.payment_page,
        name="payment",
    ),
    path("payment/callback/", views.payment_callback, name="payment_callback"),

    # Customer account
    path("account/orders/", views.order_history, name="order_history"),
    path(
        "account/orders/<str:order_number>/",
        views.order_detail,
        name="order_detail",
    ),
    path("account/profile/", views.profile, name="profile"),
    path("login/", views.StoreLoginView.as_view(), name="login"),
    path("logout/", views.StoreLogoutView.as_view(), name="logout"),
    path("register/", views.register, name="register"),

    # Admin dashboard
    path("dashboard/", views.dashboard_home, name="dashboard_home"),
    path(
        "dashboard/products/",
        views.dashboard_products,
        name="dashboard_products",
    ),
    path(
        "dashboard/products/new/",
        views.dashboard_product_create,
        name="dashboard_product_create",
    ),
    path(
        "dashboard/products/<int:pk>/edit/",
        views.dashboard_product_edit,
        name="dashboard_product_edit",
    ),
    path(
        "dashboard/products/<int:pk>/delete/",
        views.dashboard_product_delete,
        name="dashboard_product_delete",
    ),
    path(
        "dashboard/products/<int:pk>/toggle/",
        views.dashboard_product_toggle,
        name="dashboard_product_toggle",
    ),
    path(
        "dashboard/orders/",
        views.dashboard_orders,
        name="dashboard_orders",
    ),
    path(
        "dashboard/orders/<str:order_number>/",
        views.dashboard_order_detail,
        name="dashboard_order_detail",
    ),
    path(
        "dashboard/categories/",
        views.dashboard_categories,
        name="dashboard_categories",
    ),
    path(
        "dashboard/categories/<int:pk>/edit/",
        views.dashboard_category_edit,
        name="dashboard_category_edit",
    ),
    path(
        "dashboard/categories/<int:pk>/delete/",
        views.dashboard_category_delete,
        name="dashboard_category_delete",
    ),
]
