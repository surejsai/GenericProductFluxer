"""
Debug script to investigate why Strandbags URL extraction is failing.
"""

from fluxer.extractors.html_extractor import HTMLProductExtractor
import traceback

URL = "https://www.strandbags.com.au/collections/handbags/products/evity-alana-leather-canvas-crossbody-bag-3223877?variant=45359501738142"

print("=" * 80)
print("Debugging Strandbags URL Extraction")
print("=" * 80)
print(f"URL: {URL}")
print("=" * 80)

# Initialize with debug enabled
extractor = HTMLProductExtractor(
    timeout_s=60,
    max_cost="5",
    min_chars=50,  # Lower threshold to see what we get
    max_chars=5000,
    debug=True
)

try:
    print("\n[STEP 1] Attempting to fetch HTML via ScraperAPI...")
    result = extractor.extract(URL)

    print("\n" + "=" * 80)
    print("EXTRACTION RESULT")
    print("=" * 80)
    print(f"URL: {result.url}")
    print(f"Meta Title: {result.meta_title}")
    print(f"Meta Description: {result.meta_description}")
    print(f"Extraction Method: {result.extraction_method}")
    print(f"Confidence Score: {result.confidence_score:.2f}")

    if result.product_description:
        print(f"\nProduct Description Length: {len(result.product_description)} chars")
        print(f"\nProduct Description Preview (first 500 chars):")
        print("-" * 80)
        print(result.product_description[:500])
        print("-" * 80)

        if len(result.product_description) > 500:
            print(f"\n... (truncated, total length: {len(result.product_description)} chars)")
    else:
        print("\n[ERROR] No product description extracted!")
        print("\nPossible reasons:")
        print("1. ScraperAPI failed to fetch the page")
        print("2. Page structure doesn't match expected patterns")
        print("3. Content is JavaScript-rendered")
        print("4. Page returned an error or block page")

    # Check if it's a fetch failure
    if result.extraction_method in ["fetch_fail", "blocked"]:
        print(f"\n[CRITICAL] Fetch failed with method: {result.extraction_method}")
        print("This means ScraperAPI couldn't retrieve the page properly.")
        print("\nTroubleshooting steps:")
        print("1. Check if the URL is accessible in a browser")
        print("2. Try with JavaScript rendering enabled")
        print("3. Check ScraperAPI dashboard for error details")

except Exception as e:
    print("\n" + "=" * 80)
    print("EXCEPTION OCCURRED")
    print("=" * 80)
    print(f"Error: {str(e)}")
    print("\nFull traceback:")
    print(traceback.format_exc())

print("\n" + "=" * 80)
print("Debug Complete")
print("=" * 80)
