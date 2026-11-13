"""Seed the storefront with a realistic demo catalogue.

Usage:
    python manage.py seed_products
    python manage.py seed_products --force-images

The command is idempotent: products are matched by name and updated in place.
Images are downloaded from the public DummyJSON CDN. If the network is
unavailable, a generated placeholder is saved instead so the catalogue still
looks complete.
"""

from __future__ import annotations

import io
import textwrap
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.utils.text import slugify

from products.models import Category, Product

CATEGORIES = [
    {
        "name": "Electronics",
        "slug": "electronics",
        "icon": "💻",
        "description": "Laptops, audio and everyday tech.",
        "colour": (30, 64, 175),
    },
    {
        "name": "Fashion",
        "slug": "fashion",
        "icon": "👕",
        "description": "Easy-to-wear staples and statement pieces.",
        "colour": (159, 18, 57),
    },
    {
        "name": "Home & Living",
        "slug": "home-living",
        "icon": "🛋️",
        "description": "Furniture, lighting and finishing touches.",
        "colour": (120, 53, 15),
    },
    {
        "name": "Beauty",
        "slug": "beauty",
        "icon": "💄",
        "description": "Makeup and fragrance favourites.",
        "colour": (190, 24, 93),
    },
    {
        "name": "Sports",
        "slug": "sports",
        "icon": "👟",
        "description": "Footwear and gear for every session.",
        "colour": (4, 120, 87),
    },
    {
        "name": "Accessories",
        "slug": "accessories",
        "icon": "⌚",
        "description": "Watches and details that complete the look.",
        "colour": (67, 56, 202),
    },
]

# (name, category slug, brand, price, mrp, stock, featured, image URL, description)
PRODUCTS = [
    (
        'Apple MacBook Pro 14" Space Grey',
        "electronics",
        "Apple",
        "164900",
        "189900",
        12,
        True,
        "https://cdn.dummyjson.com/product-images/laptops/apple-macbook-pro-14-inch-space-grey/thumbnail.webp",
        "A 14-inch Liquid Retina XDR display, pro-grade performance and all-day battery life in a beautifully portable chassis. Ideal for design, development and creative work.",
    ),
    (
        "Asus Zenbook Pro Duo 15",
        "electronics",
        "ASUS",
        "139990",
        "159990",
        7,
        False,
        "https://cdn.dummyjson.com/product-images/laptops/asus-zenbook-pro-dual-screen-laptop/thumbnail.webp",
        "Dual-screen creativity without compromise. A stunning 4K OLED main display pairs with the ScreenPad Plus for editing, streaming and multitasking.",
    ),
    (
        "Huawei MateBook X Pro",
        "electronics",
        "Huawei",
        "119990",
        "134990",
        5,
        False,
        "https://cdn.dummyjson.com/product-images/laptops/huawei-matebook-x-pro/thumbnail.webp",
        "An ultra-light premium notebook with a near-borderless display, metal body and fast charging. Made for people who work from anywhere.",
    ),
    (
        "Lenovo Yoga 920",
        "electronics",
        "Lenovo",
        "74990",
        "89990",
        10,
        False,
        "https://cdn.dummyjson.com/product-images/laptops/lenovo-yoga-920/thumbnail.webp",
        "A flexible 2-in-1 with a 360-degree hinge, vivid touch display and long battery life. Laptop, tablet and presentation mode in one device.",
    ),
    (
        "New Dell XPS 13 9300 Laptop",
        "electronics",
        "Dell",
        "109990",
        "129990",
        8,
        False,
        "https://cdn.dummyjson.com/product-images/laptops/new-dell-xps-13-9300-laptop/thumbnail.webp",
        "Compact, confident and fast. The XPS 13 combines an edge-to-edge display, premium materials and dependable daily performance.",
    ),
    (
        "Apple AirPods (2nd generation)",
        "electronics",
        "Apple",
        "12990",
        "14900",
        30,
        True,
        "https://cdn.dummyjson.com/product-images/mobile-accessories/apple-airpods/thumbnail.webp",
        "Wireless earbuds with easy pairing, reliable connection and up to 24 hours of listening time with the charging case.",
    ),
    (
        "Blue & Black Check Shirt",
        "fashion",
        "Urban Threads",
        "1499",
        "2499",
        35,
        False,
        "https://cdn.dummyjson.com/product-images/mens-shirts/blue-%26-black-check-shirt/thumbnail.webp",
        "A soft cotton check shirt with a relaxed fit. Layer it open over a tee or button it up for a sharper everyday look.",
    ),
    (
        "Gigabyte Aorus Men T-Shirt",
        "fashion",
        "Aorus",
        "899",
        "1499",
        40,
        False,
        "https://cdn.dummyjson.com/product-images/mens-shirts/gigabyte-aorus-men-tshirt/thumbnail.webp",
        "Breathable cotton crew-neck tee with a clean graphic print. Pre-shrunk, colourfast and comfortable all day.",
    ),
    (
        "Man Plaid Shirt",
        "fashion",
        "Rugged & Co",
        "1299",
        "2199",
        24,
        False,
        "https://cdn.dummyjson.com/product-images/mens-shirts/man-plaid-shirt/thumbnail.webp",
        "Classic plaid with a modern fit. Brushed cotton feels soft from the first wear and works across seasons.",
    ),
    (
        "Man Short Sleeve Shirt",
        "fashion",
        "Coastal Club",
        "999",
        "1799",
        30,
        False,
        "https://cdn.dummyjson.com/product-images/mens-shirts/man-short-sleeve-shirt/thumbnail.webp",
        "An easy short-sleeve shirt in a lightweight weave. Breathable, wrinkle resistant and ready for warm days.",
    ),
    (
        "Men Check Shirt",
        "fashion",
        "Oxford Lane",
        "1199",
        "1999",
        28,
        False,
        "https://cdn.dummyjson.com/product-images/mens-shirts/men-check-shirt/thumbnail.webp",
        "A versatile micro-check shirt tailored for everyday wear. Pair with jeans, chinos or shorts.",
    ),
    (
        "Annibale Colombo Bed",
        "home-living",
        "Annibale Colombo",
        "189999",
        "229999",
        3,
        False,
        "https://cdn.dummyjson.com/product-images/furniture/annibale-colombo-bed/thumbnail.webp",
        "A statement bed handcrafted with premium upholstery and a solid frame. The kind of centrepiece a bedroom deserves.",
    ),
    (
        "Annibale Colombo Sofa",
        "home-living",
        "Annibale Colombo",
        "249999",
        "299999",
        2,
        True,
        "https://cdn.dummyjson.com/product-images/furniture/annibale-colombo-sofa/thumbnail.webp",
        "Deep, generous seating wrapped in premium fabric. A beautifully made sofa designed for long evenings and lazy weekends.",
    ),
    (
        "Bedside Table African Cherry",
        "home-living",
        "WoodCraft",
        "18999",
        "24999",
        9,
        False,
        "https://cdn.dummyjson.com/product-images/furniture/bedside-table-african-cherry/thumbnail.webp",
        "Solid African cherry wood with a soft-close drawer and a hand-finished surface. Small footprint, generous storage.",
    ),
    (
        "Knoll Saarinen Executive Chair",
        "home-living",
        "Knoll",
        "84999",
        "99999",
        4,
        False,
        "https://cdn.dummyjson.com/product-images/furniture/knoll-saarinen-executive-conference-chair/thumbnail.webp",
        "An iconic silhouette with supportive cushioning and a swivel base. Comfortable enough for the whole working day.",
    ),
    (
        "Table Lamp",
        "home-living",
        "Lumen Studio",
        "2499",
        "3999",
        26,
        True,
        "https://cdn.dummyjson.com/product-images/home-decoration/table-lamp/thumbnail.webp",
        "A warm, diffused glow for bedside tables and reading corners. Compact, sturdy and easy to style.",
    ),
    (
        "Essence Mascara Lash Princess",
        "beauty",
        "Essence",
        "449",
        "599",
        60,
        True,
        "https://cdn.dummyjson.com/product-images/beauty/essence-mascara-lash-princess/thumbnail.webp",
        "Builds dramatic length and volume with a clean, clump-free finish. The curved brush catches every lash.",
    ),
    (
        "Eyeshadow Palette with Mirror",
        "beauty",
        "Glam Theory",
        "1299",
        "1799",
        32,
        False,
        "https://cdn.dummyjson.com/product-images/beauty/eyeshadow-palette-with-mirror/thumbnail.webp",
        "Twelve blendable shades from soft neutrals to bold metallics, with a built-in mirror for on-the-go touch-ups.",
    ),
    (
        "Red Lipstick",
        "beauty",
        "Velvet Rouge",
        "599",
        "899",
        55,
        False,
        "https://cdn.dummyjson.com/product-images/beauty/red-lipstick/thumbnail.webp",
        "A creamy, high-pigment red that stays comfortable for hours. One swipe gives full, even colour.",
    ),
    (
        "Calvin Klein CK One Eau de Toilette",
        "beauty",
        "Calvin Klein",
        "4999",
        "6999",
        18,
        True,
        "https://cdn.dummyjson.com/product-images/fragrances/calvin-klein-ck-one/thumbnail.webp",
        "A fresh, clean unisex fragrance with citrus and green notes. Light enough for every day, distinctive enough to remember.",
    ),
    (
        "Nike Air Jordan 1 Red and Black",
        "sports",
        "Nike",
        "18999",
        "22999",
        14,
        True,
        "https://cdn.dummyjson.com/product-images/mens-shoes/nike-air-jordan-1-red-and-black/thumbnail.webp",
        "The silhouette that started it all, in a bold red and black colourway. Premium leather upper with cushioned comfort.",
    ),
    (
        "Nike Baseball Cleats",
        "sports",
        "Nike",
        "6999",
        "8999",
        16,
        False,
        "https://cdn.dummyjson.com/product-images/mens-shoes/nike-baseball-cleats/thumbnail.webp",
        "Lightweight traction and a locked-in fit for game day. Durable outsole built for quick cuts and sprints.",
    ),
    (
        "Puma Future Rider Trainers",
        "sports",
        "Puma",
        "5499",
        "7499",
        22,
        False,
        "https://cdn.dummyjson.com/product-images/mens-shoes/puma-future-rider-trainers/thumbnail.webp",
        "Retro running style with modern comfort. A breathable upper and soft midsole make these an everyday favourite.",
    ),
    (
        "Sports Sneakers Off White & Red",
        "sports",
        "Stride",
        "3499",
        "4999",
        25,
        False,
        "https://cdn.dummyjson.com/product-images/mens-shoes/sports-sneakers-off-white-%26-red/thumbnail.webp",
        "A lightweight sneaker with a padded collar and grippy outsole. Easy to wear from the gym to the street.",
    ),
    (
        "Brown Leather Belt Watch",
        "accessories",
        "Titan",
        "3999",
        "5999",
        20,
        False,
        "https://cdn.dummyjson.com/product-images/mens-watches/brown-leather-belt-watch/thumbnail.webp",
        "A classic analog watch with a genuine leather strap and a clean, readable dial. Dressed up or down with ease.",
    ),
    (
        "Longines Master Collection",
        "accessories",
        "Longines",
        "189999",
        "215000",
        3,
        False,
        "https://cdn.dummyjson.com/product-images/mens-watches/longines-master-collection/thumbnail.webp",
        "Swiss watchmaking at its most elegant. A refined dial, automatic movement and a bracelet built to last.",
    ),
    (
        "Rolex Cellini Date Black Dial",
        "accessories",
        "Rolex",
        "899999",
        "999999",
        2,
        False,
        "https://cdn.dummyjson.com/product-images/mens-watches/rolex-cellini-date-black-dial/thumbnail.webp",
        "A dress watch of rare poise, with a deep black dial, fine hands and an understated precious-metal case.",
    ),
    (
        "Rolex Datejust",
        "accessories",
        "Rolex",
        "749999",
        "849999",
        2,
        True,
        "https://cdn.dummyjson.com/product-images/mens-watches/rolex-datejust/thumbnail.webp",
        "The definitive everyday luxury watch. Timeless proportions, a date window and a bracelet that feels made to measure.",
    ),
]


class Command(BaseCommand):
    help = "Create demo categories and 28 realistic products with local images."

    def add_arguments(self, parser):
        parser.add_argument(
            "--force-images",
            action="store_true",
            help="Re-download every product image even if one already exists.",
        )

    def handle(self, *args, **options):
        force_images = options["force_images"]
        categories = self._seed_categories()
        created = 0
        updated = 0
        downloaded = 0
        placeholders = 0

        for (
            name,
            category_slug,
            brand,
            price,
            mrp,
            stock,
            featured,
            image_url,
            description,
        ) in PRODUCTS:
            product = Product.objects.filter(name=name).first()
            is_new = product is None
            if is_new:
                product = Product(name=name)

            product.category = categories[category_slug]
            product.brand = brand
            product.price = price
            product.mrp = mrp
            product.stock = stock
            product.is_featured = featured
            product.is_active = True
            product.tax_percent = 0
            product.description = description

            needs_image = (
                force_images
                or not product.image
                or not product.image.storage.exists(product.image.name)
                # A .jpg image from the seed command is a generated placeholder;
                # try the real CDN image again on the next run.
                or product.image.name.lower().endswith(".jpg")
            )
            if needs_image:
                filename = f"{slugify(name)[:70]}.webp"
                content, kind = self._image_content(
                    image_url, categories[category_slug], name
                )
                if kind == "placeholder":
                    filename = f"{slugify(name)[:70]}.jpg"
                product.image.save(filename, ContentFile(content), save=False)
                if kind == "download":
                    downloaded += 1
                else:
                    placeholders += 1
                    self.stdout.write(
                        self.style.WARNING(
                            f"  Used a generated placeholder for {name} "
                            "(image download unavailable)."
                        )
                    )

            product.save()
            if is_new:
                created += 1
            else:
                updated += 1

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                f"Catalogue ready: {created} product(s) created, {updated} updated, "
                f"{downloaded} image(s) downloaded, {placeholders} placeholder(s)."
            )
        )
        self.stdout.write(
            f"Categories: {Category.objects.count()} | "
            f"Products: {Product.objects.filter(is_active=True).count()} active"
        )

    def _seed_categories(self):
        categories = {}
        for data in CATEGORIES:
            category, _ = Category.objects.update_or_create(
                slug=data["slug"],
                defaults={
                    "name": data["name"],
                    "icon": data["icon"],
                    "description": data["description"],
                },
            )
            categories[data["slug"]] = category
        return categories

    def _image_content(self, url, category, product_name):
        """Return (bytes, kind). Falls back to a generated placeholder."""
        last_error = None
        for attempt in range(1, 4):
            try:
                request = Request(
                    url,
                    headers={
                        "User-Agent": "ClickMartSeed/1.0 (+http://localhost)",
                        "Accept": "image/*",
                    },
                )
                with urlopen(request, timeout=40) as response:
                    data = response.read()
                if data and len(data) > 800:
                    return data, "download"
                last_error = "the downloaded file was empty"
            except (HTTPError, URLError, TimeoutError, OSError) as exc:
                last_error = exc
                self.stdout.write(
                    self.style.WARNING(
                        f"  Image attempt {attempt}/3 failed for {product_name}: {exc}"
                    )
                )

        self.stdout.write(
            self.style.WARNING(
                f"  Could not download image for {product_name}: {last_error}"
            )
        )
        return self._placeholder_image(category, product_name), "placeholder"

    def _placeholder_image(self, category, product_name):
        from PIL import Image, ImageDraw

        width = height = 900
        category_data = next(
            (item for item in CATEGORIES if item["slug"] == getattr(category, "slug", "")),
            None,
        )
        colour = category_data["colour"] if category_data else (15, 23, 42)
        image = Image.new("RGB", (width, height), colour)
        draw = ImageDraw.Draw(image)

        # Gentle diagonal bands keep the placeholder from looking flat.
        for offset in range(-height, width, 90):
            draw.line(
                [(offset, 0), (offset + height, height)],
                fill=tuple(min(255, channel + 22) for channel in colour),
                width=45,
            )

        draw.rounded_rectangle(
            (60, 60, width - 60, height - 60),
            radius=36,
            outline=(255, 255, 255),
            width=3,
        )

        font = None
        for candidate in (
            Path("C:/Windows/Fonts/arialbd.ttf"),
            Path("C:/Windows/Fonts/Arial.ttf"),
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
            Path("/System/Library/Fonts/Supplemental/Arial Bold.ttf"),
        ):
            if candidate.exists():
                try:
                    from PIL import ImageFont

                    font = ImageFont.truetype(str(candidate), 46)
                    small = ImageFont.truetype(str(candidate), 28)
                    break
                except OSError:
                    font = None

        if font is None:
            from PIL import ImageFont

            font = ImageFont.load_default()
            small = font

        category_name = getattr(category, "name", "ClickMart")
        draw.text((90, 100), category_name.upper(), fill=(255, 255, 255), font=small)

        lines = textwrap.wrap(product_name, width=24)[:4]
        y = 300
        for line in lines:
            draw.text((90, y), line, fill=(255, 255, 255), font=font)
            y += 62

        draw.text(
            (90, height - 150),
            "CLICKMART",
            fill=(255, 255, 255),
            font=small,
        )

        buffer = io.BytesIO()
        image.save(buffer, format="JPEG", quality=88, optimize=True)
        return buffer.getvalue()
