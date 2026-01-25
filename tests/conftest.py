"""
Pytest configuration and fixtures for Fluxer tests.
"""
import sys
from pathlib import Path

# Add src to path for imports
project_root = Path(__file__).parent.parent
src_path = project_root / "src"
sys.path.insert(0, str(src_path))

import pytest
from fluxer.extractors.html_extractor import HTMLProductExtractor
from fluxer.models import ExtractionConfig


@pytest.fixture
def extractor():
    """Create a basic extractor for testing."""
    return HTMLProductExtractor(
        timeout_s=30,
        max_cost="5",
        min_chars=50,
        max_chars=1000,
        debug=False,
    )


@pytest.fixture
def extractor_with_debug():
    """Create an extractor with debug enabled."""
    return HTMLProductExtractor(
        timeout_s=30,
        max_cost="5",
        min_chars=50,
        max_chars=1000,
        debug=True,
    )


@pytest.fixture
def extraction_config():
    """Create a default extraction configuration."""
    return ExtractionConfig.default()


@pytest.fixture
def sample_html():
    """Sample HTML for testing."""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Test Product</title>
        <meta name="description" content="A test product description">
    </head>
    <body>
        <h1>Test Product</h1>
        <div class="description">
            <h2>Product Description</h2>
            <p>This is a test product with a detailed description for testing purposes.</p>
        </div>
    </body>
    </html>
    """


@pytest.fixture
def sample_url():
    """Sample URL for testing."""
    return "https://example.com/product/test"
