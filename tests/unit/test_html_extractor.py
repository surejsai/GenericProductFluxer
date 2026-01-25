from __future__ import annotations

import json
from fluxer.extractors.html_extractor import HTMLProductExtractor

# Sample HTML for testing (simulating different product page structures)
SAMPLE_HTML_1 = """
<!DOCTYPE html>
<html>
<head>
    <title>Premium Coffee Maker - Kitchen Appliances</title>
    <meta name="description" content="High-quality programmable coffee maker with timer and auto-brew features">
    <meta property="og:title" content="Premium Coffee Maker">
    <meta property="og:description" content="Brew perfect coffee every time with our premium coffee maker">
</head>
<body>
    <h1>Premium Coffee Maker</h1>
    <div class="product-details">
        <h2>Product Description</h2>
        <p>Experience barista-quality coffee at home with our Premium Coffee Maker.
        This state-of-the-art appliance features a programmable timer, allowing you to wake up
        to freshly brewed coffee every morning. The 12-cup capacity is perfect for families or
        entertaining guests. With its sleek stainless steel design and easy-to-clean removable
        filter, this coffee maker combines style and functionality.</p>

        <h3>Key Features</h3>
        <ul>
            <li>Programmable 24-hour timer</li>
            <li>12-cup capacity glass carafe</li>
            <li>Pause and serve function</li>
            <li>Auto shut-off after 2 hours</li>
            <li>Removable filter basket</li>
        </ul>
    </div>
</body>
</html>
"""

SAMPLE_HTML_2 = """
<!DOCTYPE html>
<html>
<head>
    <title>Wireless Bluetooth Headphones | AudioTech</title>
    <meta name="description" content="Premium noise-cancelling headphones">
</head>
<body>
    <script type="application/ld+json">
    {
        "@context": "https://schema.org/",
        "@type": "Product",
        "name": "Wireless Bluetooth Headphones",
        "description": "Immerse yourself in crystal-clear sound with our premium wireless Bluetooth headphones. Featuring advanced active noise cancellation technology, these headphones block out ambient noise for an uninterrupted listening experience. The ergonomic over-ear design provides superior comfort for extended wear, while the 30-hour battery life ensures your music never stops. Perfect for travel, work, or leisure.",
        "brand": "AudioTech"
    }
    </script>
    <h1>Wireless Bluetooth Headphones</h1>
    <div class="short-desc">Great sound quality</div>
</body>
</html>
"""

SAMPLE_HTML_3 = """
<!DOCTYPE html>
<html>
<head>
    <title>Smart Fitness Watch</title>
    <meta property="og:description" content="Track your fitness goals with advanced metrics">
</head>
<body>
    <h1>Smart Fitness Watch</h1>
    <section id="overview">
        <h2>Overview</h2>
        <p>Transform your fitness journey with the Smart Fitness Watch. This cutting-edge wearable
        technology monitors your heart rate, tracks steps, calories burned, and sleep patterns.
        The built-in GPS allows accurate tracking of your outdoor activities including running,
        cycling, and hiking. With smartphone notifications and a water-resistant design up to 50
        meters, this watch is your perfect companion for both workouts and daily life.</p>
    </section>

    <section>
        <h2>Technical Specifications</h2>
        <table>
            <tr><th>Display</th><td>1.4" AMOLED touchscreen</td></tr>
            <tr><th>Battery Life</th><td>Up to 7 days</td></tr>
            <tr><th>Water Resistance</th><td>5 ATM (50 meters)</td></tr>
            <tr><th>Sensors</th><td>Heart rate, GPS, Accelerometer, Gyroscope</td></tr>
        </table>
    </section>
</body>
</html>
"""


def test_html_extractor():
    """Test the HTML product extractor with various HTML samples."""
    extractor = HTMLProductExtractor(debug=True, min_chars=80, max_chars=1000)

    samples = [
        ("Coffee Maker", SAMPLE_HTML_1),
        ("Bluetooth Headphones", SAMPLE_HTML_2),
        ("Fitness Watch", SAMPLE_HTML_3),
    ]

    results = []

    for name, html in samples:
        print(f"\n{'='*70}")
        print(f"Testing: {name}")
        print(f"{'='*70}")

        result = extractor.extract(html)

        print(f"\n📊 Extraction Results:")
        print(f"  Meta Title: {result.meta_title or '❌ Not found'}")
        print(f"  Meta Description: {result.meta_description or '❌ Not found'}")
        print(f"  Extraction Method: {result.extraction_method or '❌ Failed'}")
        print(f"  Confidence Score: {result.confidence_score:.2f}")

        if result.product_description:
            print(f"\n📝 Product Description:")
            print(f"  {result.product_description[:300]}...")
        else:
            print(f"\n❌ No product description extracted")

        # Store results
        results.append({
            "product_name": name,
            "meta_title": result.meta_title,
            "meta_description": result.meta_description,
            "product_description": result.product_description,
            "extraction_method": result.extraction_method,
            "confidence_score": result.confidence_score,
        })

    # Output JSON
    print(f"\n\n{'='*70}")
    print("JSON OUTPUT")
    print(f"{'='*70}")
    print(json.dumps(results, indent=2, ensure_ascii=False))


def test_with_minimal_html():
    """Test with minimal HTML to verify graceful handling."""
    print(f"\n\n{'='*70}")
    print("Testing: Minimal HTML")
    print(f"{'='*70}")

    minimal_html = """
    <html>
    <head><title>Test Product</title></head>
    <body><p>Short text</p></body>
    </html>
    """

    extractor = HTMLProductExtractor(debug=True, min_chars=20)
    result = extractor.extract(minimal_html)

    print(f"\nMeta Title: {result.meta_title}")
    print(f"Meta Description: {result.meta_description}")
    print(f"Product Description: {result.product_description}")
    print(f"Method: {result.extraction_method}")


if __name__ == "__main__":
    # test_html_extractor()
    test_with_minimal_html()
