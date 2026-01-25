"""
Example: Integration of HTMLProductExtractor with existing scraping pipeline.

This demonstrates how to use HTMLProductExtractor with:
1. Pre-fetched HTML from files
2. Integration with DescriptionExtractor
3. Comparison of results
"""

from __future__ import annotations

import json
from typing import Dict, Any

# Import both extractors
from fluxer.extractors.desc_extractor import DescriptionExtractor, ExtractedDescription
from fluxer.extractors.html_extractor import HTMLProductExtractor, ProductData


def compare_extractors(url: str) -> Dict[str, Any]:
    """
    Compare results from both extractors on the same URL.

    Args:
        url: Product page URL to analyze

    Returns:
        Dictionary comparing results from both extractors
    """
    print(f"\n{'='*70}")
    print(f"Comparing Extractors for: {url}")
    print(f"{'='*70}\n")

    # Method 1: DescriptionExtractor (fetches HTML via ScraperAPI)
    print("Method 1: Using DescriptionExtractor (ScraperAPI)...")
    desc_extractor = DescriptionExtractor(debug=False, timeout_s=30)
    desc_result = desc_extractor.extract(url)

    print(f"  Meta Title: {desc_result.meta_title or 'N/A'}")
    print(f"  Meta Description: {desc_result.meta_description or 'N/A'}")
    print(f"  Method: {desc_result.method or 'Failed'}")
    print(f"  Description Length: {len(desc_result.description) if desc_result.description else 0}")

    # Method 2: HTMLProductExtractor (reuses fetched HTML)
    # In a real scenario, you'd get the HTML from DescriptionExtractor's internal fetch
    # For now, we'll demonstrate the concept
    print("\nMethod 2: Using HTMLProductExtractor (parsing only)...")
    print("  (Would reuse HTML from Method 1 in production)")

    return {
        "url": url,
        "desc_extractor": {
            "meta_title": desc_result.meta_title,
            "meta_description": desc_result.meta_description,
            "description": desc_result.description,
            "method": desc_result.method,
        },
        "comparison": "HTMLProductExtractor would process the same HTML without additional API calls"
    }


def process_saved_html_files():
    """
    Example: Process pre-saved HTML files using HTMLProductExtractor.
    This is useful when you have HTML files saved from previous scraping sessions.
    """
    print(f"\n{'='*70}")
    print("Processing Saved HTML Files")
    print(f"{'='*70}\n")

    # Sample HTML that might be saved from a previous scrape
    sample_html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Smart LED Light Bulb - EcoHome</title>
        <meta name="description" content="Energy-efficient smart LED bulb with app control">
        <meta property="og:title" content="Smart LED Light Bulb">
        <meta property="og:description" content="Control your lighting from anywhere with our smart LED bulb">
        <script type="application/ld+json">
        {
            "@context": "https://schema.org/",
            "@type": "Product",
            "name": "Smart LED Light Bulb",
            "description": "Transform your home with our smart LED light bulb. This energy-efficient bulb connects to your home WiFi network, allowing you to control brightness, color temperature, and scheduling from your smartphone. Compatible with Alexa, Google Home, and Apple HomeKit. With a lifespan of 25,000 hours and only 9W power consumption, it's the perfect eco-friendly lighting solution. Set custom lighting scenes, create schedules, and even sync with your music for immersive experiences.",
            "brand": {
                "@type": "Brand",
                "name": "EcoHome"
            }
        }
        </script>
    </head>
    <body>
        <h1>Smart LED Light Bulb</h1>
        <div class="product-container">
            <section id="details">
                <h2>Product Details</h2>
                <p>Basic product information here...</p>
            </section>
            <section>
                <h2>Specifications</h2>
                <table>
                    <tr><th>Power</th><td>9W (equivalent to 60W)</td></tr>
                    <tr><th>Brightness</th><td>800 lumens</td></tr>
                    <tr><th>Color Temperature</th><td>2700K-6500K (adjustable)</td></tr>
                    <tr><th>Lifespan</th><td>25,000 hours</td></tr>
                    <tr><th>Connectivity</th><td>WiFi 2.4GHz</td></tr>
                </table>
            </section>
        </div>
    </body>
    </html>
    """

    # Extract using HTMLProductExtractor
    extractor = HTMLProductExtractor(debug=True, min_chars=80, max_chars=1000)
    result = extractor.extract(sample_html)

    print(f"\n📊 Extraction Results:")
    print(f"  Meta Title: {result.meta_title}")
    print(f"  Meta Description: {result.meta_description[:80]}..." if result.meta_description else "  Meta Description: N/A")
    print(f"  Extraction Method: {result.extraction_method}")
    print(f"  Confidence Score: {result.confidence_score:.2f}")

    if result.product_description:
        print(f"\n📝 Product Description (first 200 chars):")
        print(f"  {result.product_description[:200]}...")
    else:
        print(f"\n❌ No product description extracted")

    return result


def batch_process_with_html_extractor():
    """
    Example: Batch process multiple HTML files.
    This demonstrates how you might process a folder of saved HTML files.
    """
    print(f"\n{'='*70}")
    print("Batch Processing Example")
    print(f"{'='*70}\n")

    # Simulate multiple HTML files
    html_files = {
        "product1.html": """
        <html>
        <head><title>Laptop Stand - Aluminum</title>
        <meta name="description" content="Ergonomic laptop stand"></head>
        <body>
            <h2>Overview</h2>
            <p>This premium aluminum laptop stand elevates your laptop to eye level,
            reducing neck strain and improving posture. The adjustable height design
            accommodates various viewing preferences, while the open design promotes
            better airflow to keep your laptop cool. Compatible with all laptop sizes
            from 10 to 17 inches. The sleek aluminum construction is both durable and
            lightweight, making it perfect for home office or travel use.</p>
        </body>
        </html>
        """,
        "product2.html": """
        <html>
        <head><title>Wireless Keyboard</title></head>
        <body>
            <div class="description">
                <h2>Product Description</h2>
                <p>Experience comfortable typing with our premium wireless keyboard.
                The low-profile keys provide a quiet, responsive typing experience
                perfect for office environments. With Bluetooth 5.0 connectivity,
                you can seamlessly switch between up to 3 devices. The rechargeable
                battery lasts up to 6 months on a single charge, and the compact
                design saves valuable desk space while maintaining full functionality.</p>
            </div>
        </body>
        </html>
        """,
    }

    extractor = HTMLProductExtractor(min_chars=60)
    results = []

    for filename, html_content in html_files.items():
        print(f"\nProcessing: {filename}")

        result = extractor.extract(html_content)

        results.append({
            "filename": filename,
            "meta_title": result.meta_title,
            "meta_description": result.meta_description,
            "description_preview": result.product_description[:100] + "..." if result.product_description else None,
            "extraction_method": result.extraction_method,
            "confidence": result.confidence_score,
        })

        print(f"  ✓ Extracted via: {result.extraction_method}")
        print(f"  ✓ Confidence: {result.confidence_score:.2f}")

    # Output JSON
    print(f"\n{'='*70}")
    print("JSON Results:")
    print(f"{'='*70}")
    print(json.dumps(results, indent=2, ensure_ascii=False))

    return results


def hybrid_approach_example(url: str):
    """
    Example: Hybrid approach using both extractors.

    1. Use DescriptionExtractor to fetch HTML (handles anti-bot measures)
    2. Use HTMLProductExtractor for additional analysis with different parameters
    """
    print(f"\n{'='*70}")
    print("Hybrid Approach Example")
    print(f"{'='*70}\n")

    print(f"URL: {url}\n")

    # Step 1: Fetch HTML using DescriptionExtractor
    print("Step 1: Fetching HTML via ScraperAPI...")
    desc_extractor = DescriptionExtractor(debug=False)

    # Note: In production, you'd extract the HTML from the internal method
    # For this example, we'll just show the concept
    desc_result = desc_extractor.extract(url)

    print(f"  Fetched successfully: {desc_result.method != 'fetch_fail'}")
    print(f"  Primary extraction method: {desc_result.method}")

    # Step 2: If you had the raw HTML, you could reprocess it
    print("\nStep 2: (In production) Reprocess HTML with different parameters...")
    print("  - Try shorter min_chars to catch brief descriptions")
    print("  - Try different semantic matching rules")
    print("  - Extract additional structured data")

    print(f"\n📊 Final Results:")
    print(f"  Meta Title: {desc_result.meta_title or 'N/A'}")
    print(f"  Meta Description: {desc_result.meta_description or 'N/A'}")
    print(f"  Description: {desc_result.description[:150] if desc_result.description else 'N/A'}...")

    return desc_result


def main():
    """Run all examples."""
    print("\n" + "="*70)
    print("HTMLProductExtractor Integration Examples")
    print("="*70)

    # Example 1: Process saved HTML files
    print("\n\n=== EXAMPLE 1: Processing Saved HTML ===")
    process_saved_html_files()

    # Example 2: Batch processing
    print("\n\n=== EXAMPLE 2: Batch Processing ===")
    batch_process_with_html_extractor()

    # Example 3: Comparison (requires SCRAPER_API_KEY)
    # Uncomment if you want to test with real URLs:
    # print("\n\n=== EXAMPLE 3: Comparing Extractors ===")
    # compare_extractors("https://www.example.com/product")

    print("\n\n" + "="*70)
    print("Examples completed!")
    print("="*70)


if __name__ == "__main__":
    main()
