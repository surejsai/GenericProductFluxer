# GenericProductFluxer - Restructuring Plan

## Current Progress

✅ **Completed:**
1. Created new package structure: `src/fluxer/`
2. Unified data models in `models.py` (ProductData, ProductHit, ExtractionConfig, AggregatedProducts)
3. Configuration management in `config.py`
4. Logging system in `logger.py`
5. Utility modules:
   - `utils/validators.py` - URL and input validation
   - `utils/text_cleaning.py` - Text cleaning and normalization

## New Package Structure

```
GenericProductFluxer/
├── src/
│   └── fluxer/                          # Main package
│       ├── __init__.py                  # Package initialization
│       ├── config.py                    # Configuration management ✅
│       ├── logger.py                    # Logging setup ✅
│       ├── models.py                    # Data models ✅
│       │
│       ├── extractors/                  # Extraction modules
│       │   ├── __init__.py
│       │   ├── base.py                  # Base extractor class
│       │   ├── html_extractor.py        # Main HTML extractor
│       │   ├── jsonld.py                # JSON-LD extraction
│       │   ├── semantic.py              # Semantic extraction
│       │   └── meta.py                  # Meta tag extraction
│       │
│       ├── fetchers/                    # HTTP fetching modules
│       │   ├── __init__.py
│       │   ├── base.py                  # Base fetcher class
│       │   └── scraper_api.py           # ScraperAPI wrapper
│       │
│       ├── search/                      # Search modules
│       │   ├── __init__.py
│       │   └── serp_processor.py        # SERP API wrapper
│       │
│       ├── api/                         # Flask API modules
│       │   ├── __init__.py
│       │   ├── app.py                   # Flask app factory
│       │   ├── routes.py                # API routes/blueprints
│       │   └── error_handlers.py        # Error handling
│       │
│       └── utils/                       # Utilities
│           ├── __init__.py             ✅
│           ├── validators.py           ✅
│           └── text_cleaning.py        ✅
│
├── templates/                           # Flask templates
│   └── index.html
│
├── tests/                               # Test suite
│   ├── __init__.py
│   ├── conftest.py                      # Pytest fixtures
│   ├── unit/
│   │   ├── test_models.py
│   │   ├── test_validators.py
│   │   ├── test_text_cleaning.py
│   │   └── test_extractors.py
│   └── integration/
│       ├── test_api.py
│       └── test_full_pipeline.py
│
├── docs/                                # Documentation
│   ├── API.md
│   ├── ARCHITECTURE.md
│   └── DEVELOPMENT.md
│
├── scripts/                             # Utility scripts
│   ├── run_dev.py
│   └── run_tests.py
│
├── pyproject.toml                       # Poetry configuration
├── .env.example                         # Example environment file
├── .gitignore
└── README.md                            # Main documentation
```

## Next Steps (In Order)

### Step 1: Consolidate Extractors (CRITICAL)
**Goal:** Merge `html_product_extractor.py` and `desc_extractor.py` into modular extractors

**Actions:**
1. Create `src/fluxer/extractors/base.py` - Abstract base class
2. Create `src/fluxer/extractors/html_extractor.py` - Main extractor with:
   - Best features from both current extractors
   - Uses composition (delegates to specific extractors)
3. Create `src/fluxer/extractors/jsonld.py` - JSON-LD specific extraction
4. Create `src/fluxer/extractors/semantic.py` - Semantic section matching
5. Create `src/fluxer/extractors/meta.py` - Meta tag extraction

**Benefits:**
- Single source of truth
- Easier to test individual extraction methods
- Can swap strategies easily
- Reduced duplication

### Step 2: Create Fetcher Abstraction
**Goal:** Separate HTML fetching from extraction logic

**Actions:**
1. Create `src/fluxer/fetchers/base.py` - Abstract fetcher
2. Create `src/fluxer/fetchers/scraper_api.py` - ScraperAPI implementation
3. Move bot detection logic to fetcher
4. Move auto-retry logic to fetcher

**Benefits:**
- Can easily add new fetching methods (Playwright, Selenium)
- Extraction logic doesn't care about fetching
- Easier to mock for testing

### Step 3: Refactor SERP Processing
**Goal:** Move SERP logic to new structure

**Actions:**
1. Copy `serp_services/get_popular_products.py` to `src/fluxer/search/serp_processor.py`
2. Update imports to use new models
3. Add proper logging
4. Remove sys.path manipulation

### Step 4: Refactor Flask App
**Goal:** Modernize Flask app with blueprints

**Actions:**
1. Create `src/fluxer/api/app.py` - App factory function
2. Create `src/fluxer/api/routes.py` - Blueprint with all routes
3. Create `src/fluxer/api/error_handlers.py` - Centralized error handling
4. Update `app.py` in root to import from new structure

**Benefits:**
- Better organization
- Easier testing
- Can have multiple blueprints (v1, v2 API)
- Proper error handling

### Step 5: Set Up Proper Testing
**Goal:** Create comprehensive test suite with pytest

**Actions:**
1. Create `tests/conftest.py` with fixtures
2. Create unit tests for each module
3. Create integration tests for API
4. Add pytest configuration to `pyproject.toml`
5. Set up test coverage reporting

**Benefits:**
- Confidence in changes
- Catch regressions early
- Better code quality

### Step 6: Update Dependencies
**Goal:** Clean up and modernize dependencies

**Actions:**
1. Remove duplicate dependencies (`serpapi` vs `google-search-results`)
2. Add development dependencies (pytest, pytest-cov, black, mypy)
3. Update version constraints to be less restrictive
4. Add optional dependencies for different use cases

### Step 7: Documentation
**Goal:** Create comprehensive documentation

**Actions:**
1. Write API documentation
2. Write architecture documentation
3. Create development guide
4. Update main README
5. Add docstrings to all public functions

### Step 8: Security Improvements
**Goal:** Remove security vulnerabilities

**Actions:**
1. Create `.env.example` without actual keys
2. Remove `.env` from git history
3. Add input validation to all API endpoints
4. Add rate limiting
5. Sanitize HTML in descriptions

## Migration Path

### Phase 1: New Structure (Non-Breaking)
1. Create new `src/fluxer/` package ✅
2. Keep old files working
3. Gradually migrate functionality
4. Add deprecation warnings to old modules

### Phase 2: Update Imports (Breaking)
1. Update `app.py` to use new imports
2. Update test files to use new imports
3. Test everything works
4. Mark old files as deprecated

### Phase 3: Remove Old Code
1. Move old files to `deprecated/` folder
2. Update documentation
3. Clean up project root
4. Final testing

## Key Principles

1. **Modularity:** Each module should have a single responsibility
2. **Testability:** All code should be easy to test
3. **Readability:** Clear naming, good docstrings, type hints
4. **Maintainability:** Avoid duplication, follow DRY principle
5. **Performance:** Don't sacrifice performance for style

## Example: New Extractor Usage

```python
from fluxer import HTMLProductExtractor, ExtractionConfig
from fluxer.logger import get_logger

logger = get_logger(__name__)

# Create configuration
config = ExtractionConfig.robust()  # Pre-configured for tough sites

# Initialize extractor
extractor = HTMLProductExtractor(config=config)

# Extract product
result = extractor.extract("https://example.com/product")

if result.is_valid():
    logger.info(f"Extracted: {result.meta_title}")
    logger.info(f"Confidence: {result.confidence_score:.2f}")
    logger.info(f"Method: {result.extraction_method}")
else:
    logger.warning("Extraction failed")
```

## Example: New API Structure

```python
from flask import Flask
from fluxer.api import create_app
from fluxer.config import Config

# Create app
app = create_app()

# Run
if __name__ == "__main__":
    app.run(
        host=Config.FLASK_HOST,
        port=Config.FLASK_PORT,
        debug=Config.FLASK_DEBUG,
    )
```

## Benefits of Restructuring

### For Development:
- ✅ Clear separation of concerns
- ✅ Easy to find code
- ✅ Simple to add new features
- ✅ Better IDE support (autocomplete, etc.)

### For Testing:
- ✅ Easy to mock dependencies
- ✅ Can test components in isolation
- ✅ Fast test execution

### For Deployment:
- ✅ Clean package structure
- ✅ Easy to install with pip
- ✅ Can build wheels/distributions
- ✅ Clear dependencies

### For Maintenance:
- ✅ Easy to understand codebase
- ✅ Changes are localized
- ✅ Less risk of breaking things
- ✅ Better onboarding for new developers

## Timeline Estimate

- **Phase 1** (New Structure): ~4 hours
- **Phase 2** (Update Imports): ~2 hours
- **Phase 3** (Remove Old): ~1 hour
- **Testing & Documentation**: ~3 hours

**Total: ~10 hours** for complete restructuring

## Questions to Address

1. **Do you want to keep both extractors initially?**
   - Or immediately consolidate?

2. **What testing framework preference?**
   - pytest (recommended) or unittest?

3. **Documentation format?**
   - Markdown, Sphinx, or both?

4. **API versioning?**
   - Do you want `/api/v1/` structure?

5. **Deployment target?**
   - Local only, or preparing for production?

## Next Actions

To continue this restructuring, I will:
1. Complete the extractor modules
2. Update Flask app to use new structure
3. Update imports throughout codebase
4. Test everything works
5. Clean up old files

**Ready to proceed?** Let me know if you want me to continue with the full restructuring or if you'd like to adjust the plan first.
