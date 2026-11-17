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

    # Alternate 20% and 30% discounts across the remaining catalog in a stable
    # order so the assignment is predictable whenever this migration runs.
    products = Product.objects.using(database).order_by("name", "pk")
    for index, product in enumerate(products.iterator()):
        mrp = product.mrp or product.price
        discount_percent = 20 if index % 2 == 0 else 30
        discounted_price = (mrp * Decimal(100 - discount_percent) / Decimal(100)).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        product.mrp = mrp
        product.price = discounted_price
        product.save(using=database, update_fields=["mrp", "price"])


class Migration(migrations.Migration):
    dependencies = [
        ("products", "0004_add_clothing_catalog"),
    ]

    operations = [
        migrations.RunPython(clean_catalog_and_apply_discounts, migrations.RunPython.noop),
    ]
