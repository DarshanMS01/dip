from decimal import Decimal

from django.db import migrations


CLOTHING_ITEMS = [
    {
        "name": "Everyday Cotton T-Shirt",
        "description": "A soft, breathable cotton tee with a comfortable everyday fit. Easy to dress up or down.",
        "image": "https://images.unsplash.com/photo-1521572163474-6864f9cf17ab?auto=format&fit=crop&w=1000&q=85",
        "price": Decimal("24.99"),
        "mrp": Decimal("34.99"),
        "stock": 40,
        "brand": "Everyday Co.",
    },
    {
        "name": "Classic Denim Jacket",
        "description": "A timeless denim layer with a versatile wash and sturdy buttons, made for year-round wear.",
        "image": "https://images.unsplash.com/photo-1543076447-215ad9ba6923?auto=format&fit=crop&w=1000&q=85",
        "price": Decimal("69.99"),
        "mrp": Decimal("89.99"),
        "stock": 18,
        "brand": "Northline",
    },
    {
        "name": "Relaxed Fit Hoodie",
        "description": "A cozy fleece hoodie with a roomy fit, adjustable drawstring, and front pocket.",
        "image": "https://images.unsplash.com/photo-1556821840-3a63f95609a7?auto=format&fit=crop&w=1000&q=85",
        "price": Decimal("49.99"),
        "mrp": Decimal("64.99"),
        "stock": 25,
        "brand": "Everyday Co.",
    },
    {
        "name": "Tailored Chino Trousers",
        "description": "Smart-casual stretch chinos with a clean tapered leg and comfortable all-day feel.",
        "image": "https://images.unsplash.com/photo-1473966968600-fa801b869a1a?auto=format&fit=crop&w=1000&q=85",
        "price": Decimal("54.99"),
        "mrp": Decimal("74.99"),
        "stock": 20,
        "brand": "Northline",
    },
    {
        "name": "Floral Summer Dress",
        "description": "A light, easy-to-wear floral dress made for sunny days, weekend plans, and holidays.",
        "image": "https://images.unsplash.com/photo-1515886657613-9f3515b0c78f?auto=format&fit=crop&w=1000&q=85",
        "price": Decimal("59.99"),
        "mrp": Decimal("79.99"),
        "stock": 16,
        "brand": "Daylight Studio",
    },
]


def add_clothing_catalog(apps, schema_editor):
    Category = apps.get_model("products", "Category")
    Product = apps.get_model("products", "Product")
    database = schema_editor.connection.alias

    clothing, _ = Category.objects.using(database).get_or_create(
        name="Clothing",
        defaults={
            "slug": "clothing",
            "description": "Everyday clothing and wardrobe essentials.",
            "icon": "👕",
        },
    )

    for item in CLOTHING_ITEMS:
        Product.objects.using(database).update_or_create(
            name=item["name"],
            defaults={
                **item,
                "category": clothing,
                "tax_percent": Decimal("0.00"),
                "is_active": True,
                "is_featured": True,
            },
        )


class Migration(migrations.Migration):
    dependencies = [
        ("products", "0003_category_alter_product_options_product_brand_and_more"),
    ]

    operations = [
        migrations.RunPython(add_clothing_catalog, migrations.RunPython.noop),
    ]
