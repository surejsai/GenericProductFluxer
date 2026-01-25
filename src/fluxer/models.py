"""
Data models for Fluxer product extraction.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, List


@dataclass(slots=True)
class ProductData:
    """
    Extracted product information from a webpage.

    Attributes:
        url: Product page URL
        meta_title: Page title from meta tags
        meta_description: Page description from meta tags
        product_description: Extracted product description/details
        extraction_method: Method used to extract description
        confidence_score: Confidence rating (0.0-1.0)
    """

    url: Optional[str] = None
    meta_title: Optional[str] = None
    meta_description: Optional[str] = None
    product_description: Optional[str] = None
    extraction_method: Optional[str] = None
    confidence_score: float = 0.0

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "url": self.url,
            "meta_title": self.meta_title,
            "meta_description": self.meta_description,
            "product_description": self.product_description,
            "extraction_method": self.extraction_method,
            "confidence_score": self.confidence_score,
        }

    def is_valid(self) -> bool:
        """Check if extraction was successful."""
        return (
            self.product_description is not None
            and len(self.product_description) > 0
            and self.confidence_score > 0.0
        )


@dataclass(slots=True)
class ProductHit:
    """
    Product hit from SERP API search results.

    Attributes:
        title: Product title
        source: Source website (e.g., "Amazon", "Best Buy")
        price: Product price as string
        link: Product URL (may be None initially)
        rating: Product rating (if available)
        reviews: Number of reviews (if available)
    """

    title: str
    source: str
    price: Optional[str] = None
    link: Optional[str] = None
    rating: Optional[float] = None
    reviews: Optional[int] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "title": self.title,
            "source": self.source,
            "price": self.price,
            "link": self.link,
            "rating": self.rating,
            "reviews": self.reviews,
        }

    def has_link(self) -> bool:
        """Check if product has a valid link."""
        return self.link is not None and len(self.link) > 0


@dataclass
class ExtractionConfig:
    """
    Configuration for product extraction.

    Attributes:
        min_chars: Minimum characters for valid description
        max_chars: Maximum characters to extract
        timeout_s: Request timeout in seconds
        max_cost: Maximum API cost per request
        device_type: Device type for ScraperAPI
        render_js: Enable JavaScript rendering
        auto_retry_with_js: Auto-retry with JS if blocked
        debug: Enable debug output
    """

    min_chars: int = 50
    max_chars: int = 2000
    timeout_s: int = 120
    max_cost: str = "10"
    device_type: str = "desktop"
    render_js: bool = False
    auto_retry_with_js: bool = True
    debug: bool = False

    @classmethod
    def default(cls) -> ExtractionConfig:
        """Create default configuration."""
        return cls()

    @classmethod
    def quick(cls) -> ExtractionConfig:
        """Create configuration for quick extraction (no JS)."""
        return cls(
            timeout_s=30,
            max_cost="5",
            auto_retry_with_js=False,
        )

    @classmethod
    def robust(cls) -> ExtractionConfig:
        """Create configuration for robust extraction (with JS)."""
        return cls(
            timeout_s=180,
            max_cost="15",
            render_js=True,
            auto_retry_with_js=True,
        )


@dataclass
class AggregatedProducts:
    """
    Aggregated product search results.

    Attributes:
        by_query: Dictionary mapping query to products
        total_count: Total number of products
    """

    by_query: dict[str, dict[str, ProductHit]] = field(default_factory=dict)

    @property
    def total_count(self) -> int:
        """Get total number of products across all queries."""
        return sum(len(products) for products in self.by_query.values())

    def get_all_products(self) -> List[ProductHit]:
        """Get flat list of all products."""
        products = []
        for query_products in self.by_query.values():
            products.extend(query_products.values())
        return products

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "by_query": {
                query: {title: hit.to_dict() for title, hit in products.items()}
                for query, products in self.by_query.items()
            },
            "total_count": self.total_count,
        }
