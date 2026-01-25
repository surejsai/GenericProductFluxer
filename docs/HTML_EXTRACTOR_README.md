# HTMLProductExtractor - NLP-Based Product Information Extractor

## Overview

`HTMLProductExtractor` is a sophisticated HTML parser that extracts product information from web pages using NLP-inspired semantic matching. Unlike `DescriptionExtractor` which fetches HTML via ScraperAPI, this extractor works directly with HTML text, making it perfect for:

- Processing pre-fetched HTML content
- Batch processing saved HTML files
- Integration with custom scraping pipelines
- Testing and development without API calls

## Features

- **Meta Tag Extraction**: Extracts meta title and meta description from various sources (standard meta tags, Open Graph, Twitter Cards)
- **NLP-Based Semantic Matching**: Uses keyword groups and semantic similarity to identify product descriptions
- **Multiple Extraction Methods**: Tries JSON-LD, JavaScript data, semantic sections, and fallback methods
- **Confidence Scoring**: Provides confidence scores based on extraction method and content quality
- **Rich Text Extraction**: Handles tables, lists, and structured content
- **Flexible Configuration**: Customizable minimum/maximum character limits

## Installation

Required dependencies:
```bash
pip install beautifulsoup4
```

## Quick Start

### Basic Usage

```python
from html_product_extractor import HTMLProductExtractor

# Initialize the extractor
extractor = HTMLProductExtractor(
    min_chars=80,      # Minimum description length
    max_chars=1200,    # Maximum description length
    debug=False        # Enable debug output
)

# Extract from HTML string
html_content = """
<html>
<head>
    <title>Premium Coffee Maker</title>
    <meta name="description" content="High-quality coffee maker">
</head>
<body>
    <h2>Product Description</h2>
    <p>Experience barista-quality coffee at home...</p>
</body>
</html>
"""

result = extractor.extract(html_content)

# Access extracted data
print(f"Title: {result.meta_title}")
print(f"Description: {result.meta_description}")
print(f"Product Info: {result.product_description}")
print(f"Method: {result.extraction_method}")
print(f"Confidence: {result.confidence_score}")
```

### Reading from File

```python
from html_product_extractor import HTMLProductExtractor

extractor = HTMLProductExtractor(debug=True)

# Read HTML from file
with open('product_page.html', 'r', encoding='utf-8') as f:
    html_content = f.read()

result = extractor.extract(html_content)
```

### Integration with Requests

```python
import requests
from html_product_extractor import HTMLProductExtractor

# Fetch HTML
response = requests.get('https://example.com/product')
html_content = response.text

# Extract product data
extractor = HTMLProductExtractor()
result = extractor.extract(html_content, url=response.url)
```

## Extraction Methods

The extractor tries multiple methods in order of reliability:

### 1. JSON-LD Structured Data (Highest Confidence: 0.95)
Extracts from `<script type="application/ld+json">` tags with `@type: "Product"`:

```html
<script type="application/ld+json">
{
  "@context": "https://schema.org/",
  "@type": "Product",
  "description": "Product description here..."
}
</script>
```

### 2. JavaScript Embedded Data (Confidence: 0.90)
Extracts from JavaScript variables:
- `window.themeConfig('product', {...})`
- `var product = {...}`
- `window.productData = {...}`

### 3. Semantic Section Matching (Confidence: 0.85)
Uses NLP-like keyword matching to find sections with headings like:
- "Description", "Product Description"
- "Details", "Product Details"
- "Overview", "Summary"
- "Features", "Key Features"
- "Specifications", "Specs"

### 4. Meta Description Fallback (Confidence: 0.60)
Uses the meta description if no better content is found.

### 5. Best Text Block (Confidence: 0.50)
Finds the largest text block in main content areas.

## Semantic Matching

The extractor uses keyword groups for intelligent matching:

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

Matching scores:
- **Exact match**: 1.0 (heading text exactly matches keyword)
- **Partial match**: 0.7 (keyword found in heading text)
- **Semantic match**: 0.5 (word overlap > 50%)

## ProductData Object

The `extract()` method returns a `ProductData` object with these fields:

| Field | Type | Description |
|-------|------|-------------|
| `meta_title` | `Optional[str]` | Page title from `<title>`, og:title, or twitter:title |
| `meta_description` | `Optional[str]` | Meta description from standard or social media tags |
| `product_description` | `Optional[str]` | Extracted product description (main content) |
| `extraction_method` | `Optional[str]` | Method used: 'jsonld', 'javascript', 'semantic_section', etc. |
| `confidence_score` | `float` | Confidence score (0.0 to 1.0) based on method and content |

## Configuration Options

```python
HTMLProductExtractor(
    min_chars=80,      # Minimum characters for valid description
    max_chars=1200,    # Maximum characters to extract (adds '…' if clipped)
    debug=False        # Print debug information during extraction
)
```

## Examples

### Example 1: E-commerce Product Page

```python
from html_product_extractor import HTMLProductExtractor

html = """
<html>
<head>
    <title>Wireless Mouse - TechStore</title>
    <meta name="description" content="Ergonomic wireless mouse">
    <meta property="og:title" content="Premium Wireless Mouse">
</head>
<body>
    <h1>Premium Wireless Mouse</h1>
    <div class="product-info">
        <h2>Description</h2>
        <p>Our premium wireless mouse features a comfortable ergonomic
        design perfect for long work sessions. With 2.4GHz wireless
        connectivity and a battery life of up to 18 months, you'll
        enjoy seamless productivity without interruptions.</p>
        <h3>Features</h3>
        <ul>
            <li>Ergonomic design</li>
            <li>18-month battery life</li>
            <li>2.4GHz wireless</li>
            <li>6 programmable buttons</li>
        </ul>
    </div>
</body>
</html>
"""

extractor = HTMLProductExtractor(debug=True)
result = extractor.extract(html)

print(f"Title: {result.meta_title}")
# Output: Premium Wireless Mouse

print(f"Description: {result.product_description[:100]}...")
# Output: Our premium wireless mouse features a comfortable ergonomic...
```

### Example 2: Processing Multiple Files

```python
import os
import json
from html_product_extractor import HTMLProductExtractor

def process_html_files(directory):
    extractor = HTMLProductExtractor(min_chars=50)
    results = []

    for filename in os.listdir(directory):
        if filename.endswith('.html'):
            filepath = os.path.join(directory, filename)

            with open(filepath, 'r', encoding='utf-8') as f:
                html = f.read()

            result = extractor.extract(html)

            results.append({
                'filename': filename,
                'title': result.meta_title,
                'description': result.product_description,
                'method': result.extraction_method,
                'confidence': result.confidence_score
            })

    return results

# Process all HTML files in a directory
results = process_html_files('./saved_pages/')
print(json.dumps(results, indent=2))
```

### Example 3: Integration with Playwright

```python
from playwright.sync_api import sync_playwright
from html_product_extractor import HTMLProductExtractor

def extract_from_url(url):
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(url)

        # Get rendered HTML
        html_content = page.content()
        browser.close()

        # Extract product data
        extractor = HTMLProductExtractor()
        return extractor.extract(html_content, url=url)

result = extract_from_url('https://example.com/product')
print(result.product_description)
```

## Comparison: DescriptionExtractor vs HTMLProductExtractor

| Feature | DescriptionExtractor | HTMLProductExtractor |
|---------|---------------------|---------------------|
| **Input** | URL (fetches HTML via ScraperAPI) | HTML text string |
| **Network Required** | Yes (API calls) | No |
| **Use Case** | Direct URL scraping | Pre-fetched HTML processing |
| **Cost** | Uses ScraperAPI credits | Free (no API) |
| **NLP Features** | Basic keyword matching | Advanced semantic matching |
| **Confidence Scores** | No | Yes |
| **Meta Tag Extraction** | Yes | Yes |

## Testing

Run the test suite:

```bash
python test_html_extractor.py
```

This will test the extractor with various HTML structures and output results.

## Advanced Usage

### Custom Semantic Keywords

You can modify the keyword groups by subclassing:

```python
class CustomExtractor(HTMLProductExtractor):
    DESCRIPTION_KEYWORDS = {
        'description': ['description', 'desc', 'about', 'what is'],
        'details': ['details', 'information', 'specs'],
        # Add your custom keywords...
    }

extractor = CustomExtractor()
```

### Adjusting Confidence Weights

```python
class TunedExtractor(HTMLProductExtractor):
    WEIGHTS = {
        'exact_match': 1.0,
        'partial_match': 0.8,  # Increased from 0.7
        'semantic_match': 0.6,  # Increased from 0.5
        'container_bonus': 0.2,
        'length_factor': 0.15,
    }

extractor = TunedExtractor()
```

## Best Practices

1. **Set appropriate min_chars**: Too low may capture navigation text; too high may miss valid descriptions
2. **Enable debug mode** during development to understand extraction flow
3. **Check confidence scores**: Scores below 0.7 may need manual review
4. **Handle missing data**: Always check if fields are `None` before using
5. **Sanitize input**: Ensure HTML is properly encoded (UTF-8 recommended)

## Troubleshooting

### No Description Found
- Enable `debug=True` to see which methods are tried
- Check if the HTML has proper structure
- Try lowering `min_chars` if content is shorter
- Verify the page isn't a bot challenge or error page

### Wrong Content Extracted
- Check the `extraction_method` field
- Review debug output to see what headings were matched
- Customize `DESCRIPTION_KEYWORDS` for your specific use case

### Low Confidence Scores
- Scores below 0.7 indicate uncertain extraction
- Consider manual review for these cases
- May indicate unusual page structure

## License

This code is part of the GenericProductFluxer project.
