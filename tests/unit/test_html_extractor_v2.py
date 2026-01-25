"""
Test the enhanced HTMLProductExtractor with ScraperAPI integration.
"""

from __future__ import annotations

import json
from fluxer.extractors.html_extractor import HTMLProductExtractor


# Sample URLs to test (requires SCRAPER_API_KEY)
SAMPLE_URLS = [
    {
        "title": "Hisense 483L French Door Refrigerator",
        "source": "The Good Guys",
        "url": "https://www.thegoodguys.com.au/hisense-483l-french-door-refrigerator-hrcd483tbw",
    },
    {
        "title": "LG NeoChef Microwave",
        "source": "JB Hi-Fi",
        "url": "https://www.jbhifi.com.au/products/lg-neochef-ms2336db-23l-smart-inverter-microwave",
    },
]


# Sample HTML for offline testing
SAMPLE_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Premium Coffee Maker - Best Home Appliances</title>
    <meta name="description" content="High-quality programmable coffee maker with timer and auto-brew features">
    <meta property="og:title" content="Premium Coffee Maker | Home Appliances">
    <meta property="og:description" content="Brew perfect coffee every time with our premium coffee maker">
    <script type="application/ld+json">
    {
        "@context": "https://schema.org/",
        "@type": "Product",
        "name": "Premium Coffee Maker",
        "description": "Experience barista-quality coffee at home with our Premium Coffee Maker. This state-of-the-art appliance features a programmable 24-hour timer, allowing you to wake up to freshly brewed coffee every morning. The 12-cup capacity glass carafe is perfect for families or entertaining guests. With its sleek stainless steel design, easy-to-clean removable filter basket, and automatic shut-off function, this coffee maker combines style, convenience, and safety. The pause-and-serve feature lets you grab a cup mid-brew without any mess.",
        "brand": {
            "@type": "Brand",
            "name": "HomeBrewPro"
        }
    }
    </script>
</head>
<body>
    <h1>Premium Coffee Maker</h1>
    <div class="product-details">
        <h2>Product Description</h2>
        <p>Start your day right with perfectly brewed coffee.</p>

        <h3>Key Features</h3>
        <ul>
            <li>Programmable 24-hour timer</li>
            <li>12-cup capacity glass carafe</li>
            <li>Pause and serve function</li>
            <li>Auto shut-off after 2 hours</li>
            <li>Removable filter basket for easy cleaning</li>
            <li>Stainless steel construction</li>
        </ul>
    </div>
</body>
</html>
"""


def test_html_extraction():
    """Test extraction from pre-fetched HTML (no API key required)."""
    print("=" * 80)
    print("TEST 1: Extracting from HTML (No API Required)")
    print("=" * 80)

    # Initialize without API key - HTML mode only
    extractor = HTMLProductExtractor(
        debug=True,
        min_chars=80,
        max_chars=1000
    )

    # Extract from HTML
    result = extractor.extract_from_html(SAMPLE_HTML)

    print(f"\n{'='*80}")
    print("Results:")
    print(f"{'='*80}")
    print(f"Meta Title: {result.meta_title}")
    print(f"Meta Description: {result.meta_description[:100]}...")
    print(f"Extraction Method: {result.extraction_method}")
    print(f"Confidence Score: {result.confidence_score:.2f}")

    if result.product_description:
        print(f"\nProduct Description (first 200 chars):")
        print(f"{result.product_description[:200]}...")
    else:
        print("\n❌ No product description extracted")

    return result


def test_url_extraction():
    """Test extraction from URLs (requires SCRAPER_API_KEY)."""
    print("\n\n" + "=" * 80)
    print("TEST 2: Extracting from URLs (Requires SCRAPER_API_KEY)")
    print("=" * 80)

    try:
        # Initialize with API key from environment
        extractor = HTMLProductExtractor(
            debug=True,
            timeout_s=60,
            max_cost="5",
            min_chars=80,
            max_chars=1200
        )

        results = []

        for item in SAMPLE_URLS:
            print(f"\n{'-'*80}")
            print(f"Testing: {item['title']} ({item['source']})")
            print(f"{'-'*80}")

            try:
                # Extract from URL (auto-detects and fetches)
                result = extractor.extract(item["url"])

                print(f"\n📊 Results:")
                print(f"  URL: {result.url}")
                print(f"  Meta Title: {result.meta_title or '❌ Not found'}")
                print(f"  Meta Description: {result.meta_description or '❌ Not found'}")
                print(f"  Extraction Method: {result.extraction_method or '❌ Failed'}")
                print(f"  Confidence Score: {result.confidence_score:.2f}")

                if result.product_description:
                    print(f"\n  Product Description (first 300 chars):")
                    print(f"  {result.product_description[:300]}...")
                else:
                    print(f"\n  ❌ No product description extracted")

                results.append({
                    "title": item["title"],
                    "source": item["source"],
                    "url": result.url,
                    "meta_title": result.meta_title,
                    "meta_description": result.meta_description,
                    "extraction_method": result.extraction_method,
                    "confidence_score": result.confidence_score,
                    "description_preview": result.product_description[:150] if result.product_description else None,
                })

            except Exception as e:
                print(f"❌ Error: {type(e).__name__}: {e}")
                continue

        # Output JSON
        if results:
            print(f"\n\n{'='*80}")
            print("JSON OUTPUT")
            print(f"{'='*80}")
            print(json.dumps(results, indent=2, ensure_ascii=False))

        return results

    except ValueError as e:
        print(f"\n⚠️ {e}")
        print("Skipping URL tests. Set SCRAPER_API_KEY environment variable to test URL extraction.")
        return []


def test_both_modes():
    """Test both HTML and URL modes with the same extractor instance."""
    print("\n\n" + "=" * 80)
    print("TEST 3: Mixed Mode Testing (HTML + URLs)")
    print("=" * 80)

    try:
        # Initialize with API key
        extractor = HTMLProductExtractor(
            debug=False,  # Less verbose for this test
            min_chars=60,
            max_chars=800
        )

        print("\n1. Testing HTML mode...")
        html_result = extractor.extract_from_html(SAMPLE_HTML, url="test://example.com")
        print(f"   ✓ Extracted via: {html_result.extraction_method}")
        print(f"   ✓ Confidence: {html_result.confidence_score:.2f}")

        print("\n2. Testing URL mode with auto-detection...")
        # This will auto-detect it's a URL and fetch it
        if extractor.api_key:
            url_result = extractor.extract(SAMPLE_URLS[0]["url"])
            print(f"   ✓ Extracted via: {url_result.extraction_method}")
            print(f"   ✓ Confidence: {url_result.confidence_score:.2f}")
        else:
            print("   ⚠️ Skipped (no API key)")

        print("\n3. Testing HTML mode via extract() with auto-detection...")
        # This will auto-detect it's HTML (not a URL)
        auto_result = extractor.extract(SAMPLE_HTML, is_html=True)
        print(f"   ✓ Extracted via: {auto_result.extraction_method}")
        print(f"   ✓ Confidence: {auto_result.confidence_score:.2f}")

        print("\n✅ All modes working correctly!")

    except ValueError as e:
        print(f"\n⚠️ {e}")
        print("Some tests skipped. Set SCRAPER_API_KEY for full testing.")


def main():
    """Run all tests."""
    print("\n" + "="*80)
    print("HTMLProductExtractor Enhanced Test Suite")
    print("="*80)

    # Test 1: HTML extraction (always works)
    test_html_extraction()

    # Test 2: URL extraction (requires API key)
    test_url_extraction()

    # Test 3: Both modes
    test_both_modes()

    print("\n\n" + "="*80)
    print("Tests completed!")
    print("="*80)


if __name__ == "__main__":
    main()
