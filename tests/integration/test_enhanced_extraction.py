"""
Test enhanced extraction with live URL fetching via ScraperAPI.
"""

from fluxer.extractors.html_extractor import HTMLProductExtractor


# Test URLs with complex nested structures
TEST_URLS = [
    # JB Hi-Fi product pages with complex nested structures
    "https://www.jbhifi.com.au/products/lg-neochef-ms2336db-23l-smart-inverter-microwave",
    "https://www.thegoodguys.com.au/omega-altise-brigadier-25mj-ng-sand-dune-heater-oabrfngsd",
    "https://www.strandbags.com.au/collections/handbags/products/evity-alana-leather-canvas-crossbody-bag-3223877?variant=45359501738142"


    # Add more test URLs here as needed
    # "https://www.thegoodguys.com.au/...",
    # "https://www.harveynorman.com.au/...",
]


def test_live_url_extraction(url):
    """Test extraction from a live URL using ScraperAPI."""
    print("=" * 80)
    print(f"Testing Live URL Extraction")
    print("=" * 80)
    print(f"URL: {url}")
    print("=" * 80)

    # Initialize extractor with ScraperAPI
    extractor = HTMLProductExtractor(
        timeout_s=120,         # Longer timeout for live requests
        max_cost="10",         # Limit API cost (JS rendering costs 5 credits)
        min_chars=50,          # Lower threshold for shorter descriptions
        max_chars=2000,        # Capture all features
        debug=True,
        auto_retry_with_js=True  # Automatically retry with JS if bot challenge detected
    )

    # Extract using URL (will fetch via ScraperAPI)
    print("\n[INFO] Fetching HTML via ScraperAPI...")
    result = extractor.extract(url)

    print(f"\n{'='*80}")
    print("Extraction Results:")
    print(f"{'='*80}")
    print(f"URL: {result.url}")
    print(f"Meta Title: {result.meta_title}")
    print(f"Meta Description: {result.meta_description}")
    print(f"Extraction Method: {result.extraction_method}")
    print(f"Confidence Score: {result.confidence_score:.2f}")

    if result.product_description:
        print(f"\n{'='*80}")
        print("Product Description:")
        print(f"{'='*80}")
        print(result.product_description)
        print(f"\n{'='*80}")
        print(f"Length: {len(result.product_description)} characters")

        # For JB Hi-Fi, check if key features are captured
        if "jbhifi.com.au" in url.lower() and "neochef" in url.lower():
            features_to_check = [
                'Sleek Minimalist Design',
                'Anti-Bacterial Coating',
                'Stable Turntable',
                'Even Defrosting',
                'Even Heating',
                'Versatile Cooking',
                'Bright Internal Lighting'
            ]

            print(f"\n{'='*80}")
            print("Feature Detection (JB Hi-Fi LG NeoChef):")
            print(f"{'='*80}")
            found_count = 0
            for feature in features_to_check:
                if feature.lower() in result.product_description.lower():
                    print(f"  [OK] {feature}")
                    found_count += 1
                else:
                    print(f"  [FAIL] {feature}")

            print(f"\nFound {found_count}/{len(features_to_check)} features")

            if found_count == len(features_to_check):
                print("\n[SUCCESS] All features extracted correctly!")
            elif found_count >= len(features_to_check) * 0.7:
                print(f"\n[PARTIAL] {found_count} features extracted (70%+)")
            else:
                print(f"\n[FAILED] Only {found_count} features extracted")
        else:
            # Generic check for other URLs
            print("\n[INFO] Generic URL - no specific feature validation")

    else:
        print("\n[FAIL] No product description extracted!")

    return result


def test_all_urls():
    """Test extraction from all configured URLs."""
    print("=" * 80)
    print("Testing Live URL Extraction from Multiple Sources")
    print("=" * 80)
    print(f"\nTotal URLs to test: {len(TEST_URLS)}\n")

    results = []

    for idx, url in enumerate(TEST_URLS, 1):
        print(f"\n{'='*80}")
        print(f"Test {idx}/{len(TEST_URLS)}")
        print(f"{'='*80}")

        try:
            result = test_live_url_extraction(url)
            results.append({
                'url': url,
                'success': result.product_description is not None,
                'method': result.extraction_method,
                'confidence': result.confidence_score,
                'length': len(result.product_description or "")
            })
        except Exception as e:
            print(f"\n[ERROR] Failed to extract from {url}")
            print(f"Error: {str(e)}")
            results.append({
                'url': url,
                'success': False,
                'error': str(e)
            })

    # Summary
    print("\n\n" + "=" * 80)
    print("Extraction Summary")
    print("=" * 80)

    for idx, res in enumerate(results, 1):
        print(f"\n{idx}. {res['url']}")
        if res['success']:
            print(f"   [OK] Method: {res['method']}, Confidence: {res['confidence']:.2f}, Length: {res['length']} chars")
        else:
            print(f"   [FAIL] {res.get('error', 'Unknown error')}")

    success_count = sum(1 for r in results if r['success'])
    print(f"\n{'='*80}")
    print(f"Success Rate: {success_count}/{len(results)} ({success_count/len(results)*100:.1f}%)")
    print(f"{'='*80}")

    return results


if __name__ == "__main__":
    # Check if SCRAPER_API_KEY is set
    import os
    from dotenv import load_dotenv

    load_dotenv()

    if not os.getenv('SCRAPER_API_KEY'):
        print("=" * 80)
        print("ERROR: SCRAPER_API_KEY not found!")
        print("=" * 80)
        print("\nPlease set your ScraperAPI key in one of these ways:")
        print("1. Create a .env file with: SCRAPER_API_KEY=your_key_here")
        print("2. Set environment variable: export SCRAPER_API_KEY=your_key_here")
        print("\nGet your API key from: https://www.scraperapi.com/")
        print("=" * 80)
        exit(1)

    # Test all configured URLs
    test_all_urls()

    print("\n\n" + "=" * 80)
    print("Testing Complete")
    print("=" * 80)
