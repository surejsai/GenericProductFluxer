# Live URL Extraction Testing

## Overview

The `test_enhanced_extraction.py` file now tests the HTML product extractor with **live URLs** using ScraperAPI integration. It fetches real HTML from product pages and extracts product descriptions.

## Prerequisites

1. **ScraperAPI Key**: You need an active ScraperAPI key
   - Sign up at: https://www.scraperapi.com/
   - Free tier available for testing

2. **Python Dependencies**:
   ```bash
   pip install requests beautifulsoup4 python-dotenv
   ```

## Setup

### Option 1: Using .env file (Recommended)

Create a `.env` file in the project root:

```bash
SCRAPER_API_KEY=your_api_key_here
```

### Option 2: Environment Variable

```bash
# Windows
set SCRAPER_API_KEY=your_api_key_here

# Linux/Mac
export SCRAPER_API_KEY=your_api_key_here
```

## Running the Test

```bash
python test_enhanced_extraction.py
```

## What It Does

1. **Checks API Key**: Validates that SCRAPER_API_KEY is configured
2. **Fetches Live HTML**: Uses ScraperAPI to fetch HTML from each URL in `TEST_URLS`
3. **Extracts Product Details**: Uses the NLP-based extractor to find product descriptions
4. **Validates Features**: For known products (like JB Hi-Fi LG NeoChef), validates specific features
5. **Reports Results**: Shows extraction method, confidence score, and success rate

## Test Configuration

Add or modify URLs in the `TEST_URLS` list:

```python
TEST_URLS = [
    # JB Hi-Fi
    "https://www.jbhifi.com.au/products/lg-neochef-ms2336db-23l-smart-inverter-microwave",

    # Add more URLs here
    "https://www.thegoodguys.com.au/...",
    "https://www.harveynorman.com.au/...",
]
```

## Expected Output

```
================================================================================
Testing Live URL Extraction from Multiple Sources
================================================================================

Total URLs to test: 1

================================================================================
Test 1/1
================================================================================
Testing Live URL Extraction
================================================================================
URL: https://www.jbhifi.com.au/products/lg-neochef-ms2336db-23l-smart-inverter-microwave
================================================================================

[INFO] Fetching HTML via ScraperAPI...
[SCRAPER] Fetching: https://www.jbhifi.com.au/...
[SCRAPER] Status: 200
[SCRAPER] Got raw HTML response

... (extraction process) ...

================================================================================
Extraction Results:
================================================================================
URL: https://www.jbhifi.com.au/...
Meta Title: LG NeoChef MS2336DB 23L Smart Inverter Microwave | JB Hi-Fi
Meta Description: LG NeoChef microwave with smart inverter technology
Extraction Method: semantic_section
Confidence Score: 0.85

================================================================================
Product Description:
================================================================================
Key Features Sleek Minimalist Design The tempered glass on the front door...
(full description with all features)

================================================================================
Length: 847 characters

================================================================================
Feature Detection (JB Hi-Fi LG NeoChef):
================================================================================
  [OK] Sleek Minimalist Design
  [OK] Anti-Bacterial Coating
  [OK] Stable Turntable
  [OK] Even Defrosting
  [OK] Even Heating
  [OK] Versatile Cooking
  [OK] Bright Internal Lighting

Found 7/7 features

[SUCCESS] All features extracted correctly!


================================================================================
Extraction Summary
================================================================================

1. https://www.jbhifi.com.au/products/lg-neochef-ms2336db-23l-smart-inverter-microwave
   [OK] Method: semantic_section, Confidence: 0.85, Length: 847 chars

================================================================================
Success Rate: 1/1 (100.0%)
================================================================================
```

## Troubleshooting

### Error: "SCRAPER_API_KEY not found!"

**Solution**: Set your API key using one of the methods in the Setup section above.

### Error: "ScraperAPI request failed"

**Possible causes**:
- Invalid API key
- API quota exceeded
- Network issues
- Website blocking ScraperAPI

**Solutions**:
1. Check your API key is correct
2. Check your ScraperAPI dashboard for quota
3. Try with a different URL
4. Increase timeout: `timeout_s=120`

### Low Confidence Scores

If extraction confidence is low (<0.6):
1. Enable debug mode to see what's being matched
2. The page structure might be unusual
3. Try adjusting `min_chars` parameter
4. Check if the page uses JavaScript rendering (use `render="true"` in ScraperAPI params)

### Incomplete Feature Extraction

If not all features are extracted:
1. Check the HTML structure in debug output
2. The page might have changed since testing
3. Adjust `max_chars` parameter if description is cut off
4. Check if content is in JavaScript (not HTML)

## Cost Considerations

ScraperAPI charges credits per request:
- Standard request: 1 credit
- JavaScript rendering: 5 credits
- Premium proxy: 10+ credits

The test uses:
- `max_cost="5"`: Limits to 5 credits per request
- `timeout_s=60`: 60-second timeout

Free tier typically includes 1,000 credits/month.

## Customization

### Test Different Products

Edit `TEST_URLS` to test different product pages:

```python
TEST_URLS = [
    "https://www.amazon.com/...",
    "https://www.bestbuy.com/...",
    "https://www.target.com/...",
]
```

### Add Custom Feature Validation

For products other than the LG NeoChef, add validation:

```python
if "amazon.com" in url.lower():
    features_to_check = [
        'Feature 1',
        'Feature 2',
        'Feature 3',
    ]
    # Validation logic
```

### Adjust Extractor Parameters

```python
extractor = HTMLProductExtractor(
    timeout_s=120,        # Longer timeout
    max_cost="10",        # Higher cost limit
    min_chars=50,         # Shorter minimum
    max_chars=5000,       # Longer maximum
    device_type="mobile", # Mobile user agent
    debug=True            # Enable debug output
)
```

## Integration with Other Scripts

You can use this test pattern in your own scripts:

```python
from html_product_extractor import HTMLProductExtractor

# Initialize
extractor = HTMLProductExtractor(timeout_s=60, debug=False)

# Extract from URL
result = extractor.extract("https://example.com/product")

# Use the data
if result.confidence_score >= 0.7:
    print(f"Title: {result.meta_title}")
    print(f"Description: {result.product_description}")
else:
    print("Low confidence - manual review needed")
```

## Comparison with Old Test

| Old Test | New Test |
|----------|----------|
| Used hardcoded HTML | Fetches live HTML via ScraperAPI |
| Static test data | Dynamic real-world testing |
| No network I/O | Real API calls |
| Instant results | ~5-15 seconds per URL |
| No API costs | Uses ScraperAPI credits |
| Limited testing | Comprehensive validation |

## Next Steps

1. Add more product URLs to `TEST_URLS`
2. Run regular tests to monitor extraction quality
3. Adjust NLP keywords if needed for specific sites
4. Use results to improve extraction algorithms
5. Integrate into CI/CD pipeline for automated testing

## Support

For issues or questions:
- Check [ENHANCED_EXTRACTOR_README.md](ENHANCED_EXTRACTOR_README.md) for extractor documentation
- Review [MIGRATION_GUIDE.md](MIGRATION_GUIDE.md) if migrating from old extractor
- Check ScraperAPI documentation: https://docs.scraperapi.com/
