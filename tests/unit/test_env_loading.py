"""
Test if environment variables are loading correctly.
"""

import os
from dotenv import load_dotenv

print("=" * 80)
print("Testing Environment Variable Loading")
print("=" * 80)

# Load .env file
load_dotenv()

# Check if key is loaded
api_key = os.getenv('SCRAPER_API_KEY')

print(f"\nSCRAPER_API_KEY loaded: {api_key is not None}")

if api_key:
    print(f"Key length: {len(api_key)}")
    print(f"Key value: {api_key}")
    print(f"First 10 chars: {api_key[:10]}")
    print(f"Last 10 chars: {api_key[-10:]}")

    # Check for quotes
    if api_key.startswith("'") or api_key.startswith('"'):
        print("\n[WARNING] Key has quotes at the start!")
    if api_key.endswith("'") or api_key.endswith('"'):
        print("[WARNING] Key has quotes at the end!")
else:
    print("[ERROR] SCRAPER_API_KEY not found!")

print("\n" + "=" * 80)
