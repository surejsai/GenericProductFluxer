"""
Data models for Fluxer product extraction.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any


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

# ============================================================================
# ENTITY EXTRACTION DATA MODELS
# ============================================================================

@dataclass
class SupportingEntity:
    """A supporting entity that clarifies the primary product."""
    name: str
    entity_type: str  # material, standard, environment, care
    why_it_matters: str

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "name": self.name,
            "type": self.entity_type,
            "why_it_matters": self.why_it_matters,
        }


@dataclass
class PlacementRecommendation:
    """Recommendation for where to place an entity on a product page."""
    entity_name: str
    entity_type: str
    recommended_sections: List[str]  # e.g., ['specs_table', 'care_instructions']
    reasoning: str

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "entity_name": self.entity_name,
            "entity_type": self.entity_type,
            "recommended_sections": self.recommended_sections,
            "reasoning": self.reasoning,
        }


@dataclass
class EntityExtractionResult:
    """Complete entity extraction results for a product."""
    product_id: str
    product_name: str
    primary_entity_path: str
    supporting_entities: List[SupportingEntity] = field(default_factory=list)
    placement_map: List[PlacementRecommendation] = field(default_factory=list)
    noise_terms: List[str] = field(default_factory=list)
    grouped_terms: Dict[str, List[str]] = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "product_id": self.product_id,
            "product_name": self.product_name,
            "primary_entity_path": self.primary_entity_path,
            "supporting_entities": [e.to_dict() for e in self.supporting_entities],
            "placement_map": [p.to_dict() for p in self.placement_map],
            "noise_terms": self.noise_terms,
            "grouped_terms": self.grouped_terms,
        }


# ============================================================================
# HYBRID ENTITY EXTRACTION DATA MODELS (Rules + LLM)
# ============================================================================

@dataclass
class EntityItem:
    """
    Individual entity with full provenance tracking.

    Attributes:
        name: Entity name (e.g., "Stainless Steel", "1200mm")
        entity_type: Type classification (material, dimension, standard, etc.)
        evidence: Text snippet supporting this entity
        source: Extraction source ("rules" or "llm")
        value: Numeric value if applicable
        unit: Unit of measurement if applicable
        why_it_matters: Explanation of entity significance
    """
    name: str
    entity_type: str
    evidence: str
    source: str  # "rules" or "llm"
    value: Optional[str] = None
    unit: Optional[str] = None
    why_it_matters: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "name": self.name,
            "type": self.entity_type,
            "evidence": self.evidence,
            "source": self.source,
            "value": self.value,
            "unit": self.unit,
            "why_it_matters": self.why_it_matters,
        }


@dataclass
class Conflict:
    """
    Conflict between rules and LLM extraction.

    Represents a case where rules and LLM produced different values
    for the same entity type.
    """
    entity_type: str
    rule_value: str
    llm_value: str
    resolution: str  # "prefer_rules", "prefer_llm", "manual_review"
    reason: str

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "entity_type": self.entity_type,
            "rule_value": self.rule_value,
            "llm_value": self.llm_value,
            "resolution": self.resolution,
            "reason": self.reason,
        }


@dataclass
class AuditInfo:
    """
    Audit trail for entity extraction.

    Tracks what happened during extraction for debugging
    and quality analysis.
    """
    missing_types: List[str] = field(default_factory=list)
    conflicts: List[Conflict] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)
    llm_invoked: bool = False
    llm_reason: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "missing_types": self.missing_types,
            "conflicts": [c.to_dict() for c in self.conflicts],
            "notes": self.notes,
            "llm_invoked": self.llm_invoked,
            "llm_reason": self.llm_reason,
        }


@dataclass
class HybridEntityExtractionResult:
    """
    Enhanced entity extraction result with rules + LLM.

    Provides complete audit trail showing what came from rules
    vs LLM, any conflicts detected, and final merged results.
    """
    product_id: str
    product_name: str
    primary_entity_path: str
    grouped_terms: Dict[str, List[str]] = field(default_factory=dict)
    rule_entities: List[EntityItem] = field(default_factory=list)
    llm_entities: List[EntityItem] = field(default_factory=list)
    supporting_entities: List[EntityItem] = field(default_factory=list)
    placement_map: List[PlacementRecommendation] = field(default_factory=list)
    noise_terms: List[str] = field(default_factory=list)
    confidence: float = 0.0
    audit: AuditInfo = field(default_factory=AuditInfo)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "product_id": self.product_id,
            "product_name": self.product_name,
            "primary_entity_path": self.primary_entity_path,
            "grouped_terms": self.grouped_terms,
            "rule_entities": [e.to_dict() for e in self.rule_entities],
            "llm_entities": [e.to_dict() for e in self.llm_entities],
            "supporting_entities": [e.to_dict() for e in self.supporting_entities],
            "placement_map": [p.to_dict() for p in self.placement_map],
            "noise_terms": self.noise_terms,
            "confidence": self.confidence,
            "audit": self.audit.to_dict(),
        }