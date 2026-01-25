# Product Extractors Comparison Guide

## Overview

Your project now has two powerful extractors for product information:

1. **DescriptionExtractor** - Fetches and extracts from URLs
2. **HTMLProductExtractor** - Extracts from HTML text with advanced NLP

## Quick Comparison

| Feature | DescriptionExtractor | HTMLProductExtractor |
|---------|---------------------|---------------------|
| **File** | `desc_extractor.py` | `html_product_extractor.py` |
| **Input** | URL string | HTML text string |
| **Fetching** | Yes (via ScraperAPI) | No (you provide HTML) |
| **API Cost** | Uses ScraperAPI credits | Free (no API calls) |
| **Meta Title** | ✅ Yes | ✅ Yes |
| **Meta Description** | ✅ Yes | ✅ Yes |
| **Product Description** | ✅ Yes | ✅ Yes |
| **NLP Features** | Basic keyword matching | Advanced semantic matching |
| **Confidence Scores** | ❌ No | ✅ Yes (0.0 - 1.0) |
| **Debug Mode** | ✅ Yes | ✅ Yes |
| **Handles Bot Challenges** | ✅ Yes (via ScraperAPI) | ❌ No (pre-fetched HTML) |

## When to Use Each Extractor

### Use DescriptionExtractor When:
- ✅ You have URLs and need to fetch HTML
- ✅ Target sites have anti-bot protection
- ✅ You need to handle JavaScript-rendered content
- ✅ You want an all-in-one solution (fetch + extract)
- ✅ You have ScraperAPI credits available

### Use HTMLProductExtractor When:
- ✅ You already have HTML content
- ✅ Processing saved HTML files
- ✅ Batch processing without API costs
- ✅ You need confidence scores
- ✅ You want more detailed semantic analysis
- ✅ Testing/development without API calls
- ✅ Integration with custom scraping tools (Playwright, Selenium, etc.)

## Usage Examples

### DescriptionExtractor (URL → Product Data)

```python
from desc_extractor import DescriptionExtractor

# Initialize
extractor = DescriptionExtractor(
    timeout_s=30,
    max_cost="5",
    min_chars=80,
    debug=True
)

# Extract from URL (fetches HTML automatically)
result = extractor.extract("https://example.com/product")

# Access results
print(result.meta_title)           # Page title
print(result.meta_description)     # Meta description
print(result.description)          # Product description
print(result.method)               # Extraction method used
```

### HTMLProductExtractor (HTML → Product Data)

```python
from html_product_extractor import HTMLProductExtractor

# Initialize
extractor = HTMLProductExtractor(
    min_chars=80,
    max_chars=1200,
    debug=True
)

# Extract from HTML text
html_content = "<html>...</html>"  # Your HTML here
result = extractor.extract(html_content)

# Access results
print(result.meta_title)           # Page title
print(result.meta_description)     # Meta description
print(result.product_description)  # Product description
print(result.extraction_method)    # Method used
print(result.confidence_score)     # Confidence (0.0-1.0)
```

## Data Models

### ExtractedDescription (DescriptionExtractor)
```python
@dataclass
class ExtractedDescription:
    url: str
    description: Optional[str]
    method: Optional[str]
    meta_title: Optional[str]
    meta_description: Optional[str]
```

### ProductData (HTMLProductExtractor)
```python
@dataclass
class ProductData:
    meta_title: Optional[str]
    meta_description: Optional[str]
    product_description: Optional[str]
    extraction_method: Optional[str]
    confidence_score: float  # 0.0 to 1.0
```

## Extraction Methods

### DescriptionExtractor Methods:
1. **javascript** - JavaScript embedded data
2. **jsonld** - JSON-LD structured data
3. **meta** - Meta description tag
4. **section** - Section by heading
5. **fallback** - Best text block

### HTMLProductExtractor Methods:
1. **jsonld** (confidence: 0.95) - JSON-LD Product schema
2. **javascript** (confidence: 0.90) - JavaScript data
3. **semantic_section** (confidence: 0.85) - NLP-based section matching
4. **meta_fallback** (confidence: 0.60) - Meta description
5. **best_block** (confidence: 0.50) - Largest text block

## NLP Semantic Matching (HTMLProductExtractor)

### Keyword Groups
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

### Scoring System
- **Exact match**: 1.0 - Heading exactly matches keyword
- **Partial match**: 0.7 - Keyword found in heading
- **Semantic match**: 0.5 - Word overlap > 50%
- **Container bonus**: +0.3 - Contains product-related words
- **Length factor**: +0.2 - Sufficient content length

## Meta Tag Extraction

Both extractors check multiple sources for meta tags:

### Meta Title Sources (Priority Order):
1. `<title>` tag
2. `<meta property="og:title">` (Open Graph)
3. `<meta name="twitter:title">` (Twitter Cards)

### Meta Description Sources (Priority Order):
1. `<meta name="description">`
2. `<meta property="og:description">` (Open Graph)
3. `<meta name="twitter:description">` (Twitter Cards)

## Integration Patterns

### Pattern 1: Simple URL Extraction
```python
from desc_extractor import DescriptionExtractor

extractor = DescriptionExtractor()
result = extractor.extract(url)
```

### Pattern 2: Offline HTML Processing
```python
from html_product_extractor import HTMLProductExtractor

with open('product.html', 'r') as f:
    html = f.read()

extractor = HTMLProductExtractor()
result = extractor.extract(html)
```

### Pattern 3: Hybrid Approach
```python
# 1. Fetch with DescriptionExtractor
desc_extractor = DescriptionExtractor()
result1 = desc_extractor.extract(url)

# 2. If you have the raw HTML, reprocess with different parameters
html_extractor = HTMLProductExtractor(min_chars=40)
result2 = html_extractor.extract(raw_html)  # Different thresholds

# Compare results and choose best one
if result2.confidence_score > 0.8:
    use_result2()
else:
    use_result1()
```

### Pattern 4: Batch Processing
```python
from html_product_extractor import HTMLProductExtractor
import os

extractor = HTMLProductExtractor()
results = []

for file in os.listdir('html_files/'):
    with open(f'html_files/{file}', 'r') as f:
        html = f.read()
    result = extractor.extract(html)
    results.append(result)
```

## Testing Files

### Test DescriptionExtractor
```bash
python test_desc_Extractor.py
```

### Test HTMLProductExtractor
```bash
python test_html_extractor.py
```

### Integration Examples
```bash
python example_integration.py
```

## Best Practices

### For DescriptionExtractor:
1. Set appropriate `max_cost` to control API spending
2. Use `timeout_s` to prevent hanging on slow sites
3. Enable `debug=True` during development
4. Check for `method="blocked"` to detect bot challenges

### For HTMLProductExtractor:
1. Adjust `min_chars` based on your content type
2. Check `confidence_score` - scores < 0.7 may need review
3. Enable `debug=True` to understand extraction process
4. Ensure HTML is properly encoded (UTF-8)

### General:
1. Always check if extracted fields are `None` before using
2. Handle exceptions gracefully
3. Test with sample data before production use
4. Monitor extraction success rates

## Cost Optimization

### Reduce API Costs:
1. **Cache HTML**: Save fetched HTML for reprocessing
   ```python
   # Fetch once
   result = desc_extractor.extract(url)
   # Save HTML somewhere
   # Later, reprocess with HTMLProductExtractor
   ```

2. **Batch Operations**: Fetch during off-peak hours, process later
   ```python
   # Fetch phase (uses API)
   for url in urls:
       html = fetch_and_save(url)

   # Process phase (free)
   for html_file in html_files:
       result = html_extractor.extract(html_file)
   ```

3. **Try HTML Extractor First**: If you have HTML from other sources
   ```python
   # If HTML available from cache/other source
   result = html_extractor.extract(cached_html)

   # Only fetch if needed
   if not result.product_description:
       result = desc_extractor.extract(url)
   ```

## Troubleshooting

### Problem: No Description Found

**DescriptionExtractor:**
- Check if site is blocking (method="blocked")
- Increase `max_cost` if needed
- Enable `debug=True` to see fetch details

**HTMLProductExtractor:**
- Enable `debug=True` to see extraction attempts
- Lower `min_chars` threshold
- Check if HTML is complete (not truncated)
- Verify page structure (headings, sections exist)

### Problem: Wrong Content Extracted

**Both Extractors:**
- Check `method` / `extraction_method` field
- Review debug output
- Try different `min_chars` / `max_chars` values

**HTMLProductExtractor:**
- Check `confidence_score` - low scores indicate uncertainty
- Customize `DESCRIPTION_KEYWORDS` for your use case

### Problem: Performance Issues

**DescriptionExtractor:**
- Reduce `timeout_s` for faster failures
- Use `max_cost` to limit expensive requests

**HTMLProductExtractor:**
- Process is fast (no network I/O)
- If slow, reduce `max_chars` to limit processing

## Summary

- **DescriptionExtractor**: Best for direct URL scraping with anti-bot handling
- **HTMLProductExtractor**: Best for processing pre-fetched HTML with advanced analysis
- **Together**: Fetch with DescriptionExtractor, analyze with HTMLProductExtractor for detailed insights
- **Both**: Extract meta title, meta description, and product descriptions effectively

Choose the right tool for your workflow!
