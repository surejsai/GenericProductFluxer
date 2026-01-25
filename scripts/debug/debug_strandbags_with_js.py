"""
Debug Strandbags extraction with JavaScript rendering enabled and higher max_cost.
"""

from fluxer.extractors.html_extractor import HTMLProductExtractor

URL = "https://www.strandbags.com.au/collections/handbags/products/evity-alana-leather-canvas-crossbody-bag-3223877?variant=45359501738142"

print("=" * 80)
print("Testing Strandbags with JS Rendering (Higher max_cost)")
print("=" * 80)
print(f"URL: {URL}")
print("=" * 80)

# Initialize with higher max_cost to allow JS rendering
extractor = HTMLProductExtractor(
    timeout_s=120,  # Longer timeout for JS rendering
    max_cost="10",  # Higher cost limit (JS rendering costs 5 credits)
    min_chars=50,
    max_chars=5000,
    debug=True,
    render_js=False,  # Start with JS disabled
    auto_retry_with_js=True  # But auto-retry with JS if blocked
)

print("\n[TEST] Attempting extraction with auto-retry enabled...")
result = extractor.extract(URL)

print("\n" + "=" * 80)
print("RESULT")
print("=" * 80)
print(f"URL: {result.url}")
print(f"Meta Title: {result.meta_title}")
print(f"Meta Description: {result.meta_description}")
print(f"Extraction Method: {result.extraction_method}")
print(f"Confidence Score: {result.confidence_score:.2f}")

if result.product_description:
    print(f"\n[SUCCESS] Product description extracted!")
    print(f"Length: {len(result.product_description)} chars")
    print(f"\nFirst 500 characters:")
    print("-" * 80)
    print(result.product_description[:500])
    print("-" * 80)

    if len(result.product_description) > 500:
        print(f"\n... (showing first 500 of {len(result.product_description)} total chars)")
else:
    print(f"\n[FAILED] No product description extracted")
    print(f"Extraction method: {result.extraction_method}")

print("\n" + "=" * 80)
