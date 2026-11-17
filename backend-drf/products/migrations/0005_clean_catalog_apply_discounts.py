from decimal import Decimal, ROUND_HALF_UP

from django.db import migrations


CLOTHING_CATEGORIES = ("Clothing", "Fashion")


def clean_catalog_and_apply_discounts(apps, schema_editor):
    Category = apps.get_model("products", "Category")
    Product = apps.get_model("products", "Product")
    database = schema_editor.connection.alias

    # Remove apparel products and their now-unused categories from the catalog.
    Product.objects.using(database).filter(
        category__name__in=CLOTHING_CATEGORIES
    ).delete()
    Category.objects.using(database).filter(name__in=CLOTHING_CATEGORIES).delete()

    # Apply a fixed 20% discount to all remaining catalog items.
    products = Product.objects.using(database).order_by("name", "pk")
    for product in products.iterator():
        base_price = product.mrp or product.price
        discounted_price = (base_price * Decimal("0.80")).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        product.mrp = base_price
        product.price = discounted_price
        product.save(using=database, update_fields=["mrp", "price"])


class Migration(migrations.Migration):
    dependencies = [
        ("products", "0004_add_clothing_catalog"),
    ]

    operations = [
        migrations.RunPython(clean_catalog_and_apply_discounts, migrations.RunPython.noop),
    ]
