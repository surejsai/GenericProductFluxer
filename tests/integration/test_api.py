"""
Simple test script to verify the Flask API endpoints.
"""
import requests
import json

BASE_URL = "http://localhost:5000"

def test_search():
    """Test the search endpoint."""
    print("=" * 80)
    print("Testing /api/search endpoint")
    print("=" * 80)

    response = requests.post(
        f"{BASE_URL}/api/search",
        json={"query": "wireless headphones"},
        timeout=30
    )

    print(f"Status Code: {response.status_code}")

    if response.status_code == 200:
        data = response.json()
        print(f"Status: {data['status']}")
        print(f"Query: {data.get('query')}")
        print(f"Products Found: {data.get('count')}")

        if data.get('products'):
            print("\nFirst Product:")
            product = data['products'][0]
            print(f"  Title: {product.get('title')}")
            print(f"  Price: {product.get('price')}")
            print(f"  Source: {product.get('source')}")
            print(f"  Link: {product.get('link', 'N/A')[:50]}...")

        return data.get('products', [])
    else:
        print(f"Error: {response.text}")
        return []


def test_extract(url):
    """Test the extract endpoint."""
    print("\n" + "=" * 80)
    print("Testing /api/extract endpoint")
    print("=" * 80)
    print(f"URL: {url}")

    response = requests.post(
        f"{BASE_URL}/api/extract",
        json={"url": url},
        timeout=120
    )

    print(f"Status Code: {response.status_code}")

    if response.status_code == 200:
        data = response.json()
        result = data.get('data', {})

        print(f"Status: {data['status']}")
        print(f"\nExtracted Data:")
        print(f"  Meta Title: {result.get('meta_title', 'N/A')[:60]}...")
        print(f"  Meta Description: {result.get('meta_description', 'N/A')[:60]}...")
        print(f"  Description Length: {len(result.get('product_description', '') or '')}")
        print(f"  Extraction Method: {result.get('extraction_method')}")
        print(f"  Confidence Score: {result.get('confidence_score'):.2f}")

        if result.get('product_description'):
            desc = result['product_description']
            print(f"\nDescription Preview:")
            print(f"  {desc[:150]}...")
    else:
        print(f"Error: {response.text}")


def test_full_flow():
    """Test the complete flow: search → extract."""
    print("\n" + "=" * 80)
    print("TESTING COMPLETE FLOW")
    print("=" * 80)

    # Step 1: Search
    products = test_search()

    if not products:
        print("\nNo products found. Cannot continue.")
        return

    # Step 2: Extract from first product
    first_product = products[0]
    if first_product.get('link'):
        test_extract(first_product['link'])
    else:
        print("\nFirst product has no link. Cannot extract.")


if __name__ == "__main__":
    try:
        print("Fluxer Atelier API Test")
        print("Make sure the Flask app is running at http://localhost:5000")
        print()

        # Test the complete flow
        test_full_flow()

        print("\n" + "=" * 80)
        print("Test Complete!")
        print("=" * 80)

    except requests.exceptions.ConnectionError:
        print("\nError: Could not connect to Flask app.")
        print("Make sure the app is running: python app.py")
    except Exception as e:
        print(f"\nError: {e}")
