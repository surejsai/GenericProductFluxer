# Strandbags URL Extraction - Problem & Solution

## Problem

The Strandbags URL was failing to extract product information with the error:
```
[FAIL] Unknown error
Success Rate: 0/1 (0.0%)
```

## Root Causes Identified

### 1. Missing Dependency: `python-dotenv`
**Issue**: The `python-dotenv` package was not installed, so the `.env` file containing `SCRAPER_API_KEY` was not being loaded.

**Symptoms**:
- ScraperAPI key was not found
- Extraction failed with "ScraperAPI key not configured" error

**Fix**: Installed `python-dotenv`:
```bash
pip install python-dotenv
```

### 2. Bot Challenge Detection
**Issue**: Strandbags website uses Cloudflare protection that returns a challenge page on first request without JavaScript rendering.

**Symptoms**:
- ScraperAPI returned HTML with bot challenge indicators
- Extractor marked the page as "blocked"

**Fix**: Added automatic retry with JavaScript rendering when bot challenge is detected.

### 3. Overly Sensitive Bot Challenge Detection
**Issue**: The bot challenge detection was too sensitive - it flagged pages that contained the words "captcha" or "solve" anywhere in the HTML, even in JavaScript code or configuration.

**Symptoms**:
- Pages with JavaScript rendering enabled were still being flagged as blocked
- Even after successfully fetching the page, it was rejected

**Fix**: Made bot challenge detection more specific:
- Only flag short pages (< 3000 chars) with obvious block phrases
- For longer pages, look for very specific challenge patterns
- Ignore generic words like "captcha" unless in specific context

### 4. Insufficient API Cost Limit
**Issue**: JavaScript rendering costs 5 credits per request, but the test was configured with `max_cost="5"`, which sometimes wasn't enough.

**Symptoms**:
- ScraperAPI returned 403 error: "This request exceeds your max_cost"
- Retry with JavaScript failed

**Fix**: Increased `max_cost` to "10" in test configuration to allow for JavaScript rendering.

## Changes Made

### 1. Updated `html_product_extractor.py`

#### Added Parameters for JavaScript Rendering:
```python
def __init__(
    self,
    *,
    # ... existing parameters ...
    render_js: bool = False,           # NEW: Enable JS rendering
    auto_retry_with_js: bool = True,   # NEW: Auto-retry with JS if blocked
) -> None:
```

#### Enhanced `extract()` Method with Auto-Retry Logic:
```python
# Check for bot challenges
if self._looks_like_bot_challenge(fetched_html):
    if self.debug:
        print("[SCRAPER] [WARN] Detected bot challenge page")

    # Retry with JavaScript rendering if auto-retry is enabled
    if self.auto_retry_with_js and not self.render_js:
        if self.debug:
            print("[SCRAPER] [INFO] Retrying with JavaScript rendering enabled...")

        fetched_html_js = self._fetch_html_scraperapi(input_str, retry_with_js=True)

        if fetched_html_js and not self._looks_like_bot_challenge(fetched_html_js):
            if self.debug:
                print("[SCRAPER] [OK] Retry with JS succeeded!")
            return self._extract_from_html(fetched_html_js, url=input_str)
```

#### Updated `_fetch_html_scraperapi()` Method:
```python
def _fetch_html_scraperapi(self, url: str, retry_with_js: bool = False) -> Optional[str]:
    """
    Fetch HTML via ScraperAPI with proper response handling.

    Args:
        url: URL to fetch
        retry_with_js: If True, force JavaScript rendering (used for retries)
    """
    # Use JS rendering if explicitly requested or if retry_with_js is True
    render = "true" if (self.render_js or retry_with_js) else "false"

    payload = {
        "api_key": self.api_key,
        "url": url,
        "device_type": self.device_type,
        "render": render,
    }
```

#### Improved `_looks_like_bot_challenge()` Method:
```python
def _looks_like_bot_challenge(self, html: str) -> bool:
    """
    Check if HTML appears to be a bot/CAPTCHA challenge page.
    Be conservative - only flag obvious challenge pages.
    """
    h = (html or "").lower()

    # If page is very short (< 3000 chars), it's likely a block page
    if len(h) < 3000:
        # Check for common block indicators
        if any(phrase in h for phrase in [
            "access denied",
            "checking your browser",
            "just a moment",
            "please enable javascript to continue"
        ]):
            return True

    # For longer pages, look for very specific challenge patterns
    # that wouldn't appear in normal product pages
    specific_challenges = [
        "checking your browser before accessing" in h,
        ("verify you are human" in h and len(h) < 10000),
        ("please complete the captcha" in h and len(h) < 10000),
        ("cloudflare" in h and "ray id" in h and len(h) < 15000),
    ]

    return any(specific_challenges)
```

### 2. Updated `test_enhanced_extraction.py`

```python
# Initialize extractor with ScraperAPI
extractor = HTMLProductExtractor(
    timeout_s=120,         # Longer timeout for JS rendering
    max_cost="10",         # Higher cost limit (JS rendering costs 5 credits)
    min_chars=50,          # Lower threshold for shorter descriptions
    max_chars=2000,
    debug=True,
    auto_retry_with_js=True  # Automatically retry with JS if blocked
)
```

## Results

### Before Fix:
```
1. https://www.strandbags.com.au/...
   [FAIL] Unknown error

Success Rate: 0/1 (0.0%)
```

### After Fix:
```
1. https://www.strandbags.com.au/...
   [OK] Method: jsonld, Confidence: 0.95, Length: 162 chars

Success Rate: 1/1 (100.0%)
```

## How It Works Now

1. **First Attempt**: Try fetching without JavaScript (faster, cheaper)
2. **Bot Detection**: Check if response is a challenge page
3. **Auto-Retry**: If blocked and `auto_retry_with_js=True`, retry with JavaScript rendering
4. **Success**: Extract product information from successfully fetched HTML

## Flow Diagram

```
URL Request
    |
    v
Fetch HTML (JS disabled)
    |
    v
Bot Challenge Detected?
    |
    +-- No --> Extract Product Data ✓
    |
    +-- Yes --> auto_retry_with_js enabled?
                |
                +-- No --> Return "blocked" ✗
                |
                +-- Yes --> Fetch HTML (JS enabled)
                           |
                           v
                       Bot Challenge Detected?
                           |
                           +-- No --> Extract Product Data ✓
                           |
                           +-- Yes --> Return "blocked" ✗
```

## Configuration Recommendations

### For Sites with Bot Protection (Strandbags, Cloudflare-protected sites):
```python
extractor = HTMLProductExtractor(
    timeout_s=120,              # JS rendering takes longer
    max_cost="10",              # Allow for JS rendering (5 credits)
    auto_retry_with_js=True,    # Auto-retry with JS if blocked
    debug=True                  # See what's happening
)
```

### For Simple Sites (No Bot Protection):
```python
extractor = HTMLProductExtractor(
    timeout_s=30,               # Faster timeout
    max_cost="5",               # Lower cost
    auto_retry_with_js=False,   # No retry needed
    render_js=False             # No JS needed
)
```

### For Sites That Always Need JS:
```python
extractor = HTMLProductExtractor(
    timeout_s=120,
    max_cost="10",
    render_js=True,             # Always use JS rendering
    auto_retry_with_js=False    # No retry needed (already using JS)
)
```

## Cost Considerations

| Configuration | Credits per Request | When to Use |
|--------------|-------------------|-------------|
| `render_js=False` | 1 credit | Simple sites, no bot protection |
| `render_js=False, auto_retry_with_js=True` | 1-6 credits | Sites that might have bot protection |
| `render_js=True` | 5 credits | Sites that always need JavaScript |

## Testing

To test Strandbags or similar protected sites:

```bash
# Run the test suite
python test_enhanced_extraction.py

# Debug a specific URL
python debug_strandbags_with_js.py
```

## Summary

The Strandbags URL extraction was failing due to:
1. Missing `python-dotenv` dependency
2. Bot challenge protection on the website
3. Overly sensitive bot detection
4. Insufficient API cost limit

All issues have been resolved with:
1. Installed `python-dotenv`
2. Added automatic retry with JavaScript rendering
3. Improved bot challenge detection logic
4. Increased `max_cost` to support JavaScript rendering

**Success Rate: 100%** ✓
