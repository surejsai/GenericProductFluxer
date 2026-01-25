# Enhanced HTMLProductExtractor - Complete Guide

## Overview

The **HTMLProductExtractor** is now a unified, intelligent product information extractor that combines:

1. **ScraperAPI Integration** - Fetches HTML from URLs with anti-bot protection
2. **Advanced NLP Semantic Matching** - Superior understanding of webpage structure
3. **Dual Mode Operation** - Works with both URLs and pre-fetched HTML
4. **Confidence Scoring** - Provides reliability metrics for extracted data

This makes it the **most powerful extractor** in your toolkit, replacing the need for separate extractors.

---

## Key Advantages Over `desc_extractor.py`

| Feature | desc_extractor.py | **HTMLProductExtractor** |
|---------|-------------------|--------------------------|
| ScraperAPI Integration | ✅ Yes | ✅ Yes |
| Works with Pre-fetched HTML | ❌ No | ✅ Yes |
| **NLP Semantic Matching** | ❌ Basic | ✅ **Advanced** |
| **Confidence Scores** | ❌ No | ✅ **Yes (0.0-1.0)** |
| Keyword Groups | Fixed list | **Expandable semantic groups** |
| Scoring Algorithm | Token similarity | **Multi-factor NLP scoring** |
| Auto URL/HTML Detection | ❌ No | ✅ **Yes** |
| Flexible | Single mode | **Dual mode** |

---

## Installation

### Required Dependencies

```bash
pip install requests beautifulsoup4 python-dotenv
```

### Optional: ScraperAPI Key

For URL fetching, set your ScraperAPI key:

```bash
# In .env file
SCRAPER_API_KEY=your_key_here

# Or in code
extractor = HTMLProductExtractor(scraperapi_key="your_key_here")
```

---

## Quick Start

### Mode 1: Extract from URL (with ScraperAPI)

```python
from html_product_extractor import HTMLProductExtractor

# Initialize with API key (from env or parameter)
extractor = HTMLProductExtractor(
    timeout_s=30,
    max_cost="5",
    debug=True
)

# Extract from URL (auto-fetches)
result = extractor.extract("https://example.com/product")

# Access results
print(f"Title: {result.meta_title}")
print(f"Description: {result.product_description}")
print(f"Method: {result.extraction_method}")
print(f"Confidence: {result.confidence_score}")
```

### Mode 2: Extract from HTML (No API Required)

```python
from html_product_extractor import HTMLProductExtractor

# Initialize without API key
extractor = HTMLProductExtractor(
    min_chars=80,
    max_chars=1200,
    debug=True
)

# Read HTML from file or other source
with open('product_page.html', 'r', encoding='utf-8') as f:
    html_content = f.read()

# Extract from HTML
result = extractor.extract_from_html(html_content, url="https://example.com")

# Results available immediately
print(f"Extracted via: {result.extraction_method}")
print(f"Confidence: {result.confidence_score:.2f}")
```

### Mode 3: Auto-Detection

```python
extractor = HTMLProductExtractor()

# Automatically detects URL and fetches
result1 = extractor.extract("https://example.com/product")

# Automatically detects HTML content
html = "<html>...</html>"
result2 = extractor.extract(html, is_html=True)
```

---

## Advanced NLP Features

### Semantic Keyword Groups

The extractor uses sophisticated keyword groups for intelligent matching:

```python
DESCRIPTION_KEYWORDS = {
    'description': ['description', 'desc', 'describe', 'about'],
    'details': ['details', 'detail', 'information', 'info'],
    'overview': ['overview', 'summary', 'introduction', 'intro'],
    'features': ['features', 'feature', 'key features', 'highlights'],
    'specifications': ['specifications', 'specs', 'specification', 'technical'],
    'product': ['product', 'item', 'article'],
}
```

### Multi-Factor Scoring System

```python
WEIGHTS = {
    'exact_match': 1.0,      # Heading exactly matches keyword
    'partial_match': 0.7,    # Keyword found in heading
    'semantic_match': 0.5,   # Word overlap > 50%
    'container_bonus': 0.3,  # Contains product-related words
    'length_factor': 0.2,    # Sufficient content length
}
```

### How It Works

1. **Exact Match** (Score: 1.0)
   ```html
   <h2>Description</h2>  <!-- Matches 'description' exactly -->
   ```

2. **Partial Match** (Score: 0.7)
   ```html
   <h2>Product Description</h2>  <!-- Contains 'description' -->
   ```

3. **Semantic Match** (Score: 0.5)
   ```html
   <h2>Product Details and Information</h2>  <!-- Word overlap with 'product details' -->
   ```

4. **Container Bonus** (+0.15)
   ```html
   <h2>Item Details</h2>  <!-- Contains 'item' keyword -->
   ```

5. **Length Bonus** (+0.3 max)
   ```
   Longer descriptions get higher scores
   ```

---

## Extraction Methods & Confidence

The extractor tries multiple methods in order of reliability:

### 1. JSON-LD Structured Data (Confidence: 0.95)

Most reliable. Extracts from `<script type="application/ld+json">`:

```html
<script type="application/ld+json">
{
  "@context": "https://schema.org/",
  "@type": "Product",
  "description": "Premium wireless headphones with noise cancellation..."
}
</script>
```

**Why High Confidence**: Standardized schema, explicitly labeled

### 2. JavaScript Embedded Data (Confidence: 0.90)

Extracts from JavaScript variables:

```javascript
window.productData = {
    description: "Premium wireless headphones..."
};
```

**Why High Confidence**: Programmatic data, structured format

### 3. Semantic Section Matching (Confidence: 0.85)

**This is where the NLP shines!** Uses advanced semantic matching to find description sections:

```html
<section>
    <h2>Product Overview</h2>  <!-- Semantic score: 0.85 -->
    <p>Premium wireless headphones offer exceptional sound...</p>
</section>
```

**Why Good Confidence**: Intelligent matching, considers context

### 4. Meta Description Fallback (Confidence: 0.60)

Uses meta description if nothing better found:

```html
<meta name="description" content="Premium headphones...">
```

**Why Lower Confidence**: Often marketing copy, may be short

### 5. Best Text Block (Confidence: 0.50)

Last resort - finds largest text block in main content:

```html
<article>
    <p>Long product description text...</p>
</article>
```

**Why Lowest Confidence**: No semantic understanding, just size

---

## Configuration Options

```python
HTMLProductExtractor(
    # ScraperAPI Settings (optional)
    scraperapi_key=None,          # API key (or use env SCRAPER_API_KEY)
    timeout_s=30,                 # Request timeout
    device_type="desktop",        # "desktop" or "mobile"
    max_cost="5",                 # Max API credits per request

    # Extraction Settings
    min_chars=80,                 # Minimum description length
    max_chars=1200,               # Maximum description length
    debug=False                   # Enable debug output
)
```

---

## ProductData Object

```python
@dataclass
class ProductData:
    url: Optional[str]                    # Source URL (if available)
    meta_title: Optional[str]             # Page title
    meta_description: Optional[str]       # Meta description
    product_description: Optional[str]    # Extracted description
    extraction_method: Optional[str]      # Method used
    confidence_score: float               # 0.0 to 1.0
```

### Example

```python
result = extractor.extract(url)

print(result.url)                    # https://example.com/product
print(result.meta_title)             # "Premium Headphones | AudioStore"
print(result.meta_description)       # "Best wireless headphones..."
print(result.product_description)    # "Experience premium audio..."
print(result.extraction_method)      # "semantic_section"
print(result.confidence_score)       # 0.87
```

---

## Complete Examples

### Example 1: E-commerce Scraping

```python
from html_product_extractor import HTMLProductExtractor
import json

# Product URLs to scrape
urls = [
    "https://store1.com/product1",
    "https://store2.com/product2",
    "https://store3.com/product3",
]

extractor = HTMLProductExtractor(
    timeout_s=60,
    max_cost="5",
    min_chars=100,
    debug=False
)

results = []
for url in urls:
    print(f"Processing: {url}")

    result = extractor.extract(url)

    # Only keep high-confidence results
    if result.confidence_score >= 0.7:
        results.append({
            "url": result.url,
            "title": result.meta_title,
            "description": result.product_description,
            "confidence": result.confidence_score,
            "method": result.extraction_method
        })
    else:
        print(f"  ⚠️ Low confidence ({result.confidence_score:.2f}), skipping")

# Save results
with open('products.json', 'w') as f:
    json.dump(results, f, indent=2)
```

### Example 2: Batch Processing Saved HTML

```python
from html_product_extractor import HTMLProductExtractor
import os

# No API key needed for HTML mode
extractor = HTMLProductExtractor(min_chars=60)

html_dir = './saved_html/'
results = []

for filename in os.listdir(html_dir):
    if not filename.endswith('.html'):
        continue

    filepath = os.path.join(html_dir, filename)
    print(f"Processing: {filename}")

    with open(filepath, 'r', encoding='utf-8') as f:
        html = f.read()

    result = extractor.extract_from_html(html, url=filename)

    results.append({
        "file": filename,
        "title": result.meta_title,
        "method": result.extraction_method,
        "confidence": result.confidence_score,
        "description_length": len(result.product_description or "")
    })

# Print summary
print(f"\n{'='*60}")
print(f"Processed {len(results)} files")
print(f"Average confidence: {sum(r['confidence'] for r in results) / len(results):.2f}")
```

### Example 3: Confidence-Based Fallback

```python
from html_product_extractor import HTMLProductExtractor

extractor = HTMLProductExtractor(debug=True)

url = "https://example.com/product"
result = extractor.extract(url)

# Use confidence score to decide
if result.confidence_score >= 0.85:
    print("✅ High confidence - use as-is")
    description = result.product_description

elif result.confidence_score >= 0.60:
    print("⚠️ Medium confidence - may need review")
    description = result.product_description
    # Maybe flag for human review

else:
    print("❌ Low confidence - use fallback")
    # Use meta description or other fallback
    description = result.meta_description or "No description available"

print(f"\nFinal description: {description[:200]}...")
```

### Example 4: Custom Semantic Keywords

```python
from html_product_extractor import HTMLProductExtractor

class CustomExtractor(HTMLProductExtractor):
    # Add your custom keywords
    DESCRIPTION_KEYWORDS = {
        'description': ['description', 'desc', 'about', 'what is this'],
        'details': ['details', 'info', 'information', 'learn more'],
        'overview': ['overview', 'summary', 'intro'],
        'features': ['features', 'benefits', 'advantages'],
        'specifications': ['specs', 'technical specs', 'tech specs'],
        'product': ['product', 'item', 'offering'],
    }

    # Adjust weights if needed
    WEIGHTS = {
        'exact_match': 1.0,
        'partial_match': 0.8,  # Increased from 0.7
        'semantic_match': 0.6,  # Increased from 0.5
        'container_bonus': 0.3,
        'length_factor': 0.2,
    }

extractor = CustomExtractor()
result = extractor.extract(url)
```

---

## Testing

### Run Tests

```bash
# Test HTML extraction (no API key required)
python test_html_extractor.py

# Test all modes including URL fetching (requires API key)
python test_html_extractor_v2.py
```

### Test Output

```
================================================================================
TEST 1: Extracting from HTML (No API Required)
================================================================================
[META] Title: Premium Coffee Maker - Best Home Appliances...
[META] Description: High-quality programmable coffee maker...
[EXTRACT] ✓ Found via jsonld

================================================================================
Results:
================================================================================
Meta Title: Premium Coffee Maker | Home Appliances
Meta Description: Brew perfect coffee every time...
Extraction Method: jsonld
Confidence Score: 0.95

Product Description (first 200 chars):
Experience barista-quality coffee at home with our Premium Coffee Maker...
```

---

## Troubleshooting

### Issue: "ScraperAPI key not configured"

**Solution**: Set environment variable or pass key in code:

```python
# Option 1: Environment variable
export SCRAPER_API_KEY=your_key

# Option 2: In code
extractor = HTMLProductExtractor(scraperapi_key="your_key")

# Option 3: Use HTML-only mode
extractor = HTMLProductExtractor()  # No key needed
result = extractor.extract_from_html(html_content)
```

### Issue: Low confidence scores

**Possible causes**:
- Unusual page structure
- No semantic headings
- Short content

**Solutions**:
1. Lower `min_chars` threshold
2. Enable `debug=True` to see what's being matched
3. Customize `DESCRIPTION_KEYWORDS`
4. Check if content is JavaScript-rendered (use `render="true"` in ScraperAPI)

### Issue: Wrong content extracted

**Solution**: Check extraction method and adjust:

```python
result = extractor.extract(url)

if result.extraction_method == "best_block":
    # Least reliable - might need custom extraction
    print("Consider customizing DESCRIPTION_KEYWORDS")

elif result.extraction_method == "meta_fallback":
    # Using meta description - often too short
    print("Page might lack proper structure")
```

### Issue: No description found

**Debug steps**:

```python
extractor = HTMLProductExtractor(debug=True)
result = extractor.extract(url)

# Check what was tried
# Debug output will show:
# - Which methods were attempted
# - Why each method failed
# - What headings were found and their scores
```

---

## Migration from desc_extractor.py

### Old Code (desc_extractor.py)

```python
from desc_extractor import DescriptionExtractor

extractor = DescriptionExtractor(
    timeout_s=30,
    max_cost="5",
    debug=True
)

result = extractor.extract(url)
print(result.description)
```

### New Code (html_product_extractor.py)

```python
from html_product_extractor import HTMLProductExtractor

extractor = HTMLProductExtractor(
    timeout_s=30,
    max_cost="5",
    debug=True
)

result = extractor.extract(url)
print(result.product_description)  # Note: field name changed
print(f"Confidence: {result.confidence_score}")  # NEW: confidence scoring!
```

### Key Differences

1. **Import name**: `DescriptionExtractor` → `HTMLProductExtractor`
2. **Result field**: `result.description` → `result.product_description`
3. **New features**: `confidence_score`, better NLP, dual-mode operation

---

## Best Practices

### 1. Use Confidence Scores

```python
if result.confidence_score >= 0.8:
    use_directly(result.product_description)
elif result.confidence_score >= 0.6:
    queue_for_review(result)
else:
    use_fallback(result.meta_description)
```

### 2. Set Appropriate Thresholds

```python
# For short descriptions (reviews, summaries)
extractor = HTMLProductExtractor(min_chars=50)

# For detailed descriptions
extractor = HTMLProductExtractor(min_chars=150)
```

### 3. Enable Debug During Development

```python
# Development
extractor = HTMLProductExtractor(debug=True)

# Production
extractor = HTMLProductExtractor(debug=False)
```

### 4. Handle Errors Gracefully

```python
try:
    result = extractor.extract(url)

    if result.extraction_method in ["fetch_fail", "blocked"]:
        logger.warning(f"Failed to fetch {url}")
        return None

    if result.confidence_score < 0.5:
        logger.info(f"Low confidence for {url}")

    return result

except Exception as e:
    logger.error(f"Extraction error: {e}")
    return None
```

### 5. Batch with Rate Limiting

```python
import time

for url in urls:
    result = extractor.extract(url)
    process_result(result)
    time.sleep(1)  # Respect rate limits
```

---

## Summary

**HTMLProductExtractor** is now your all-in-one solution for product data extraction:

✅ **Dual Mode**: URLs (ScraperAPI) + Pre-fetched HTML
✅ **Advanced NLP**: Semantic matching with configurable keywords
✅ **Confidence Scoring**: Know how reliable your data is
✅ **Flexible**: Works with or without API key
✅ **Intelligent**: Multi-factor scoring algorithm
✅ **Production-Ready**: Error handling, debugging, extensible

**When to use**:
- ✅ Scraping product pages from e-commerce sites
- ✅ Processing saved HTML files
- ✅ Building product catalogs
- ✅ Data enrichment pipelines
- ✅ Any scenario requiring reliable product information extraction

Start using it today for superior extraction results!
