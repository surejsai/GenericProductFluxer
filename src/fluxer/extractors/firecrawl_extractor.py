"""
Firecrawl-based product extractor.

Uses Firecrawl API for intelligent product data extraction with LLM-powered parsing.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Optional, List, Dict, Any

import requests

try:
    from dotenv import load_dotenv
except ModuleNotFoundError:
    def load_dotenv() -> None:
        return None

load_dotenv()

# Use project logger for consistent logging
from ..logger import get_logger
logger = get_logger(__name__)


@dataclass(slots=True)
class FirecrawlProductData:
    """Extracted product information from Firecrawl."""
    url: Optional[str] = None
    product_name: Optional[str] = None
    price: Optional[str] = None
    features: Optional[List[Dict[str, str]]] = None
    additional_information: Optional[str] = None
    product_description: Optional[str] = None  # Combined description for compatibility
    meta_title: Optional[str] = None
    meta_description: Optional[str] = None
    extraction_method: str = "firecrawl"
    confidence_score: float = 0.0
    credits_used: int = 0
    raw_response: Optional[Dict[str, Any]] = None


class FirecrawlProductExtractor:
    """
    Extract product information using Firecrawl API.

    Firecrawl uses LLM-powered extraction to intelligently parse product pages
    and extract structured data including features, specifications, and descriptions.

    Features:
    - LLM-powered intelligent extraction
    - Structured JSON output with custom schema
    - Handles complex e-commerce pages
    - Built-in caching support
    """

    # Firecrawl API endpoint (v2 for structured extraction)
    API_URL = "https://api.firecrawl.dev/v2/scrape"

    # Default extraction schema for product pages
    DEFAULT_SCHEMA = {
        "type": "object",
        "properties": {
            "product_name": {
                "type": "string"
            },
            "price": {
                "type": "string"
            },
            "features": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "heading": {
                            "type": "string"
                        },
                        "description": {
                            "type": "string"
                        }
                    }
                }
            },
            "additional_information": {
                "type": "string"
            }
        }
    }

    DEFAULT_PROMPT = """Extract product_name and price.
In main product details (Description/Overview/Product details/Specs tabs/accordions), extract ALL feature items (bullets/lines/cards). For each item, heading=item label/text; description=all text that belongs to it (until next item/heading) or "" if none.
If main details missing, fallback to sidebar key features.
additional_information = remaining description paragraphs."""

    def __init__(
        self,
        *,
        api_key: Optional[str] = None,
        timeout_s: int = 60,
        max_age_ms: int = 172800000,  # 2 days cache
        only_main_content: bool = False,
        custom_schema: Optional[Dict] = None,
        custom_prompt: Optional[str] = None,
    ) -> None:
        """
        Initialize the Firecrawl product extractor.

        Args:
            api_key: Firecrawl API key (optional, can use env var FIRECRAWL_API_KEY)
            timeout_s: Request timeout in seconds
            max_age_ms: Maximum cache age in milliseconds (default 2 days)
            only_main_content: Whether to extract only main content
            custom_schema: Custom JSON schema for extraction
            custom_prompt: Custom extraction prompt
        """
        self.api_key = api_key or os.getenv("FIRECRAWL_API_KEY")
        self.timeout_s = timeout_s
        self.max_age_ms = max_age_ms
        self.only_main_content = only_main_content
        self.schema = custom_schema or self.DEFAULT_SCHEMA
        self.prompt = custom_prompt or self.DEFAULT_PROMPT

    def extract(self, url: str) -> FirecrawlProductData:
        """
        Extract product data from URL using Firecrawl API.

        Args:
            url: Product page URL to extract from

        Returns:
            FirecrawlProductData object with extracted information
        """
        if not url or not url.strip():
            logger.error("No URL provided for extraction")
            return FirecrawlProductData()

        url = url.strip()

        if not self.api_key:
            logger.error("Firecrawl API key not configured. Set FIRECRAWL_API_KEY environment variable.")
            return FirecrawlProductData(url=url)

        try:
            return self._fetch_and_extract(url)
        except Exception as e:
            logger.error("Firecrawl extraction failed for %s: %s", url, e, exc_info=True)
            return FirecrawlProductData(
                url=url,
                extraction_method="firecrawl_error",
                confidence_score=0.0
            )

    def _fetch_and_extract(self, url: str) -> FirecrawlProductData:
        """Fetch and extract product data using Firecrawl API."""
        # Firecrawl v2 API payload format with JSON extraction
        payload = {
            "url": url,
            "onlyMainContent": self.only_main_content,
            "maxAge": self.max_age_ms,
            "formats": [
                {
                    "type": "json",
                    "schema": self.schema,
                    "prompt": self.prompt
                }
            ]
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        logger.info("FIRECRAWL Requesting extraction for: %s", url)
        logger.debug("FIRECRAWL Payload: %s", json.dumps(payload, indent=2))

        response = requests.post(
            self.API_URL,
            json=payload,
            headers=headers,
            timeout=self.timeout_s
        )

        logger.info("FIRECRAWL Response status: %d", response.status_code)

        if response.status_code != 200:
            logger.error("FIRECRAWL API error: status=%d, response=%s",
                        response.status_code, response.text[:1000])
            return FirecrawlProductData(
                url=url,
                extraction_method="firecrawl_api_error",
                confidence_score=0.0
            )

        response_data = response.json()
        logger.debug("FIRECRAWL Raw response: %s", json.dumps(response_data, indent=2)[:2000])

        # Firecrawl v1 returns data directly or wrapped in "data" key
        if response_data.get("success") and "data" in response_data:
            data = response_data["data"]
        elif "data" in response_data:
            data = response_data["data"]
        else:
            # Fallback for direct response format
            data = response_data

        return self._parse_response(url, data)

    def _parse_response(self, url: str, data: Dict[str, Any]) -> FirecrawlProductData:
        """Parse Firecrawl API response into ProductData."""
        # Firecrawl v2 returns JSON extraction in "json" key directly or nested
        json_data = (
            data.get("json", {}) or
            data.get("extract", {}) or
            data.get("llm_extraction", {}) or
            {}
        )
        metadata = data.get("metadata", {})

        logger.info("FIRECRAWL Parsing response - extract data: %s", json_data)
        logger.debug("FIRECRAWL Metadata: %s", metadata)

        # Extract main fields
        product_name = json_data.get("product_name")
        price = json_data.get("price")
        features = json_data.get("features") or []  # Handle None explicitly
        additional_info = json_data.get("additional_information")

        logger.info("FIRECRAWL Extracted - product_name: %s, price: %s, features count: %d",
                   product_name, price, len(features) if features else 0)

        # Build combined product description as a natural paragraph
        # Combining heading, description from features, and additional_information
        description_parts = []

        # Process features into readable sentences
        if features:
            for feature in features:
                if isinstance(feature, dict):
                    heading = (feature.get("heading") or "").strip()
                    desc = (feature.get("description") or "").strip()
                    if heading and desc:
                        # Combine heading and description into a sentence
                        description_parts.append(f"{heading}: {desc}")
                    elif heading:
                        description_parts.append(heading)
                    elif desc:
                        description_parts.append(desc)
                elif isinstance(feature, str) and feature.strip():
                    description_parts.append(feature.strip())

        # Add additional information as part of the paragraph
        if additional_info and additional_info.strip():
            description_parts.append(additional_info.strip())

        # Combine all parts into a flowing paragraph
        product_description = ". ".join(description_parts) if description_parts else None

        # Clean up the description (remove double periods, extra spaces)
        if product_description:
            product_description = product_description.replace("..", ".").replace("  ", " ")
            # Ensure it ends with a period
            if not product_description.endswith("."):
                product_description += "."

        # Validate the description is not an error page
        if product_description and self._is_error_page(product_description):
            logger.warning("FIRECRAWL Detected error page content, marking as failed extraction")
            product_description = None

        logger.info("FIRECRAWL Built product_description: %s",
                   product_description[:200] if product_description else "NONE")

        # Extract metadata
        meta_title = metadata.get("title")
        meta_description = metadata.get("description")
        credits_used = metadata.get("creditsUsed", 0)

        # Calculate confidence score (0 if no valid description)
        confidence = self._calculate_confidence(json_data, metadata) if product_description else 0.0

        logger.info("FIRECRAWL Extraction complete for %s: product=%s, features=%d, confidence=%.2f",
                   url, product_name[:30] if product_name else 'N/A',
                   len(features), confidence)

        return FirecrawlProductData(
            url=url,
            product_name=product_name,
            price=price,
            features=features,
            additional_information=additional_info,
            product_description=product_description,
            meta_title=meta_title,
            meta_description=meta_description,
            extraction_method="firecrawl",
            confidence_score=confidence,
            credits_used=credits_used,
            raw_response=data
        )

    def _is_error_page(self, description: str) -> bool:
        """Check if the description content is actually an error page."""
        if not description:
            return False

        desc_lower = description.lower()

        # Common error page patterns
        error_patterns = [
            "access denied",
            "you don't have permission",
            "you do not have permission",
            "403 forbidden",
            "404 not found",
            "page not found",
            "error 403",
            "error 404",
            "error 500",
            "internal server error",
            "service unavailable",
            "temporarily unavailable",
            "access to this page has been denied",
            "permission denied",
            "unauthorized access",
            "blocked",
            "captcha",
            "verify you are human",
            "cloudflare",
            "ray id",
            "please enable cookies",
            "enable javascript",
            "browser check",
        ]

        for pattern in error_patterns:
            if pattern in desc_lower:
                # Additional check: error pages are usually short
                if len(description) < 500:
                    return True
                # Or if it's a dominant part of the content
                if description.lower().count(pattern) > 0 and len(description) < 1000:
                    return True

        return False

    def _calculate_confidence(self, json_data: Dict, metadata: Dict) -> float:
        """Calculate confidence score based on extraction quality."""
        score = 0.5  # Base score for successful API call

        # Boost for having product name
        if json_data.get("product_name"):
            score += 0.15

        # Boost for having price
        if json_data.get("price"):
            score += 0.1

        # Boost for having features
        features = json_data.get("features", [])
        if features:
            score += min(0.15, len(features) * 0.03)  # Up to 0.15 for 5+ features

        # Boost for additional information
        if json_data.get("additional_information"):
            score += 0.1

        # Check if it was a cache hit (slightly lower confidence for stale data)
        if metadata.get("cacheState") == "hit":
            score -= 0.05

        return min(score, 1.0)


__all__ = ['FirecrawlProductExtractor', 'FirecrawlProductData']
