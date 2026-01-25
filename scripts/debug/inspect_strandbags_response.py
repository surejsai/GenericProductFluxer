"""
Inspect what ScraperAPI is actually returning for Strandbags.
"""

import requests
import os
from dotenv import load_dotenv

load_dotenv()

URL = "https://www.strandbags.com.au/collections/handbags/products/evity-alana-leather-canvas-crossbody-bag-3223877?variant=45359501738142"

api_key = os.getenv('SCRAPER_API_KEY')

print("=" * 80)
print("Inspecting ScraperAPI Response for Strandbags")
print("=" * 80)

# Try with JS rendering
payload = {
    "api_key": api_key,
    "url": URL,
    "device_type": "desktop",
    "render": "true",
    "max_cost": "10"
}

print(f"\nFetching with JS rendering enabled...")
r = requests.get("https://api.scraperapi.com/", params=payload, timeout=120)

print(f"Status: {r.status_code}")
print(f"Content length: {len(r.text)}")

# Save to file for inspection
with open('strandbags_response.html', 'w', encoding='utf-8') as f:
    f.write(r.text)

print(f"Response saved to: strandbags_response.html")

# Check for bot challenge indicators
html_lower = r.text.lower()
indicators = {
    "captcha": "captcha" in html_lower,
    "checking browser": "checking your browser" in html_lower,
    "just a moment": "just a moment" in html_lower,
    "access denied": "access denied" in html_lower,
    "enable javascript": "please enable javascript" in html_lower and "to continue" in html_lower,
    "cloudflare": "cloudflare" in html_lower,
}

print("\nBot Challenge Indicators:")
for name, found in indicators.items():
    status = "[FOUND]" if found else "[OK]   "
    print(f"  {status} {name}")

# Check for product indicators
product_indicators = {
    "product": "product" in html_lower,
    "price": "price" in html_lower,
    "add to cart": "add to cart" in html_lower or "add to bag" in html_lower,
    "description": "description" in html_lower,
}

print("\nProduct Page Indicators:")
for name, found in product_indicators.items():
    status = "[FOUND]" if found else "[MISSING]"
    print(f"  {status} {name}")

# Show first 2000 chars
print("\nFirst 2000 characters of response:")
print("=" * 80)
print(r.text[:2000])
print("=" * 80)
