# Migration Guide: desc_extractor.py → html_product_extractor.py

## Overview

The enhanced `HTMLProductExtractor` now includes all functionality from `desc_extractor.py` **PLUS** advanced NLP capabilities, making it the superior choice for all product extraction tasks.

---

## Why Migrate?

| Feature | desc_extractor.py | HTMLProductExtractor |
|---------|-------------------|----------------------|
| ScraperAPI Support | ✅ | ✅ |
| HTML-only Mode | ❌ | ✅ **NEW** |
| NLP Semantic Matching | Basic | ✅ **Advanced** |
| Confidence Scores | ❌ | ✅ **NEW** |
| Customizable Keywords | Fixed | ✅ **Expandable** |
| Multi-factor Scoring | ❌ | ✅ **NEW** |
| Auto URL/HTML Detection | ❌ | ✅ **NEW** |

**Bottom line**: `HTMLProductExtractor` does everything `desc_extractor` does, but better and with more features.

---

## Quick Migration

### Step 1: Update Import

```python
# OLD
from desc_extractor import DescriptionExtractor, ExtractedDescription

# NEW
from html_product_extractor import HTMLProductExtractor, ProductData
```

### Step 2: Update Initialization

```python
# OLD
extractor = DescriptionExtractor(
    timeout_s=30,
    max_cost="5",
    min_chars=80,
    max_chars=1200,
    debug=True
)

# NEW - Same parameters work!
extractor = HTMLProductExtractor(
    timeout_s=30,
    max_cost="5",
    min_chars=80,
    max_chars=1200,
    debug=True
)
```

### Step 3: Update Result Field Names

```python
# OLD
result = extractor.extract(url)
print(result.description)        # Old field name
print(result.method)              # Old field name

# NEW
result = extractor.extract(url)
print(result.product_description)  # New field name
print(result.extraction_method)    # New field name
print(result.confidence_score)     # NEW FEATURE!
```

---

## Side-by-Side Comparison

### Example: Basic URL Extraction

#### OLD Code (desc_extractor.py)

```python
from desc_extractor import DescriptionExtractor

extractor = DescriptionExtractor(debug=True)
result = extractor.extract("https://example.com/product")

if result.description:
    print(f"Found: {result.description[:200]}")
    print(f"Method: {result.method}")
else:
    print("No description found")
```

#### NEW Code (html_product_extractor.py)

```python
from html_product_extractor import HTMLProductExtractor

extractor = HTMLProductExtractor(debug=True)
result = extractor.extract("https://example.com/product")

if result.product_description:
    print(f"Found: {result.product_description[:200]}")
    print(f"Method: {result.extraction_method}")
    print(f"Confidence: {result.confidence_score:.2f}")  # NEW!
else:
    print("No description found")
```

**Changes**:
1. Import name
2. `result.description` → `result.product_description`
3. `result.method` → `result.extraction_method`
4. **BONUS**: `result.confidence_score` available

---

## Field Mapping

### ExtractedDescription → ProductData

| Old Field (ExtractedDescription) | New Field (ProductData) | Notes |
|----------------------------------|-------------------------|-------|
| `url` | `url` | ✅ Same |
| `description` | `product_description` | 🔄 Renamed |
| `method` | `extraction_method` | 🔄 Renamed |
| `meta_title` | `meta_title` | ✅ Same |
| `meta_description` | `meta_description` | ✅ Same |
| ❌ Not available | `confidence_score` | ✨ **NEW** |

---

## Migration Patterns

### Pattern 1: Simple Replacement

**Before**:
```python
from desc_extractor import DescriptionExtractor

def extract_product(url):
    extractor = DescriptionExtractor()
    result = extractor.extract(url)
    return result.description
```

**After**:
```python
from html_product_extractor import HTMLProductExtractor

def extract_product(url):
    extractor = HTMLProductExtractor()
    result = extractor.extract(url)
    return result.product_description
```

### Pattern 2: With Confidence Checking

**Before**:
```python
result = extractor.extract(url)
if result.description:
    save_to_database(result.description)
```

**After** (with confidence):
```python
result = extractor.extract(url)
if result.product_description and result.confidence_score >= 0.7:
    save_to_database(result.product_description, result.confidence_score)
elif result.product_description:
    queue_for_review(result.product_description, result.confidence_score)
```

### Pattern 3: Batch Processing

**Before**:
```python
from desc_extractor import DescriptionExtractor

extractor = DescriptionExtractor()

for url in urls:
    result = extractor.extract(url)
    results.append({
        'url': url,
        'description': result.description,
        'method': result.method
    })
```

**After**:
```python
from html_product_extractor import HTMLProductExtractor

extractor = HTMLProductExtractor()

for url in urls:
    result = extractor.extract(url)
    results.append({
        'url': url,
        'description': result.product_description,
        'method': result.extraction_method,
        'confidence': result.confidence_score  # NEW!
    })
```

---

## New Capabilities

### 1. HTML-Only Mode (No API Key Required)

**Not possible with desc_extractor**:
```python
# desc_extractor REQUIRES API key and URL
extractor = DescriptionExtractor()
# Can't extract from HTML directly!
```

**Now possible**:
```python
extractor = HTMLProductExtractor()  # No API key needed

# Extract from pre-fetched HTML
html = get_html_from_cache(product_id)
result = extractor.extract_from_html(html)
```

### 2. Confidence-Based Decision Making

**Not possible before**:
```python
# desc_extractor has no confidence scores
result = extractor.extract(url)
# How reliable is this? Unknown!
```

**Now possible**:
```python
result = extractor.extract(url)

if result.confidence_score >= 0.85:
    status = "high_confidence"
elif result.confidence_score >= 0.60:
    status = "medium_confidence"
else:
    status = "low_confidence"

save_with_status(result.product_description, status)
```

### 3. Auto URL/HTML Detection

**Not possible before**:
```python
# desc_extractor only accepts URLs
extractor = DescriptionExtractor()
# Can't handle HTML strings
```

**Now possible**:
```python
extractor = HTMLProductExtractor()

# Auto-detects URL
result1 = extractor.extract("https://example.com/product")

# Auto-detects HTML
result2 = extractor.extract("<html>...</html>", is_html=True)
```

---

## Testing Your Migration

### 1. Create Test Script

```python
# test_migration.py
from html_product_extractor import HTMLProductExtractor

def test_basic_extraction():
    """Test that basic extraction still works"""
    extractor = HTMLProductExtractor()

    # Test with a known URL
    result = extractor.extract("https://example.com/product")

    assert result.url is not None
    assert result.meta_title is not None
    assert result.product_description is not None
    assert result.extraction_method is not None
    assert 0.0 <= result.confidence_score <= 1.0

    print("✅ Basic extraction test passed")

if __name__ == "__main__":
    test_basic_extraction()
```

### 2. Compare Results

```python
# compare_extractors.py
from desc_extractor import DescriptionExtractor
from html_product_extractor import HTMLProductExtractor

url = "https://example.com/product"

# Old extractor
old_extractor = DescriptionExtractor()
old_result = old_extractor.extract(url)

# New extractor
new_extractor = HTMLProductExtractor()
new_result = new_extractor.extract(url)

print("OLD Extractor:")
print(f"  Description length: {len(old_result.description or '')}")
print(f"  Method: {old_result.method}")

print("\nNEW Extractor:")
print(f"  Description length: {len(new_result.product_description or '')}")
print(f"  Method: {new_result.extraction_method}")
print(f"  Confidence: {new_result.confidence_score:.2f}")
```

---

## Checklist for Migration

- [ ] Update imports: `DescriptionExtractor` → `HTMLProductExtractor`
- [ ] Update result field: `result.description` → `result.product_description`
- [ ] Update result field: `result.method` → `result.extraction_method`
- [ ] Add ProductData import if using type hints
- [ ] Consider adding confidence score checks
- [ ] Test with sample URLs
- [ ] Update any database schemas if storing method names
- [ ] Update tests
- [ ] Update documentation

---

## Common Issues

### Issue 1: AttributeError: 'ProductData' object has no attribute 'description'

**Cause**: Using old field name

**Fix**:
```python
# ❌ OLD
print(result.description)

# ✅ NEW
print(result.product_description)
```

### Issue 2: AttributeError: 'ProductData' object has no attribute 'method'

**Cause**: Using old field name

**Fix**:
```python
# ❌ OLD
print(result.method)

# ✅ NEW
print(result.extraction_method)
```

### Issue 3: Need Both Extractors During Transition

**Solution**: Use both temporarily

```python
try:
    from html_product_extractor import HTMLProductExtractor
    extractor = HTMLProductExtractor()
    result = extractor.extract(url)
    description = result.product_description
except ImportError:
    from desc_extractor import DescriptionExtractor
    extractor = DescriptionExtractor()
    result = extractor.extract(url)
    description = result.description
```

---

## Gradual Migration Strategy

### Phase 1: Side-by-Side (Low Risk)

```python
# Keep both extractors running
from desc_extractor import DescriptionExtractor
from html_product_extractor import HTMLProductExtractor

old_extractor = DescriptionExtractor()
new_extractor = HTMLProductExtractor()

# Use old as primary, new for comparison
old_result = old_extractor.extract(url)
new_result = new_extractor.extract(url)

# Log differences
if old_result.description != new_result.product_description:
    log_difference(url, old_result, new_result)

# Use old result (no risk)
return old_result.description
```

### Phase 2: Confidence-Based Switch (Medium Risk)

```python
# Use new extractor with confidence-based fallback
new_result = new_extractor.extract(url)

if new_result.confidence_score >= 0.75:
    return new_result.product_description
else:
    # Fallback to old extractor
    old_result = old_extractor.extract(url)
    return old_result.description
```

### Phase 3: Full Migration (Production Ready)

```python
# Use only new extractor
extractor = HTMLProductExtractor()
result = extractor.extract(url)

# Handle low confidence
if result.confidence_score < 0.60:
    log_low_confidence(url, result)

return result.product_description
```

---

## FAQ

**Q: Can I use both extractors in the same project?**
A: Yes! They don't conflict. Useful during gradual migration.

**Q: Will the new extractor give different results?**
A: Possibly. The NLP may find better descriptions in some cases. Use confidence scores to evaluate.

**Q: Do I need to change my API key?**
A: No. Both use the same ScraperAPI key from `SCRAPER_API_KEY` env variable.

**Q: What if I don't have an API key?**
A: The new extractor can work without one (HTML-only mode). The old one cannot.

**Q: Should I delete desc_extractor.py?**
A: Keep it during migration. Delete once fully migrated and tested.

**Q: Is the new extractor slower?**
A: Slightly slower due to advanced NLP, but the difference is negligible (milliseconds). The better accuracy is worth it.

---

## Summary

✅ **Minimal changes required** - mostly field name updates
✅ **Backward compatible** - same API parameters
✅ **Enhanced capabilities** - confidence scores, dual modes
✅ **Better accuracy** - advanced NLP semantic matching
✅ **Future-proof** - more features, actively developed

**Recommendation**: Start migration today. The benefits far outweigh the minimal effort required.

---

## Get Help

If you encounter issues during migration:

1. Enable `debug=True` to see what's happening
2. Check field name mappings above
3. Compare results with old extractor
4. Review the [ENHANCED_EXTRACTOR_README.md](ENHANCED_EXTRACTOR_README.md) for detailed documentation

Good luck with your migration! 🚀
