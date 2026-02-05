"""
SEO Description Generator using OpenAI ChatGPT.

Generates a single SEO-optimized product description paragraph using
combined extracted product data and TF-IDF keywords.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
import json

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

from ..logger import get_logger

logger = get_logger(__name__)


# System message for ChatGPT
SYSTEM_MESSAGE = """You are a professional ecommerce SEO copywriter.
Write accurate, natural product descriptions and key features in Australian English.
Write like you're explaining the product to an 18-year-old in simple, everyday language.
Never invent facts."""


# User prompt template
USER_PROMPT_TEMPLATE = """Write ONE SEO-friendly product description (150-300 words) AND key feature bullets in Australian English.

=== FACTS (what the product actually is - ONLY source of truth) ===

PRODUCT DATA:
{product_data}
- Title, specs, features, materials, dimensions
- Use ONLY this for factual claims

Analysis DATA:
Price: {price}
Generic type: {product_name}
Source text: {source_text}

=== LANGUAGE (how to describe it - vocabulary only, NOT facts) ===

Keywords (competitive vocabulary to use naturally):
{keywords_list}

Entities (semantic patterns for SEO):
{entities_section}

=== HOW TO WRITE ===

Facts vs Language:
- PRODUCT DATA = what to claim (specs, features, materials)
- Keywords/Entities = how to phrase it (vocabulary, semantic terms)
- Never claim features not in PRODUCT DATA, even if in Keywords

Description (150-300 words):
- Start with what the product is and its main purpose
- Describe key specifications and features from PRODUCT DATA
- Include usage context and scenarios where relevant
- Weave in Keywords/Entities naturally for semantic SEO
- Write for both search engines (semantic relevance) and humans (readability)
- Use simple, everyday language
- Break into 1-3 natural paragraphs if it flows better, if sufficient data exist

Key Features:
- Extract the most important and relevant features from PRODUCT DATA
- Focus on quality over quantity - only include meaningful features
- Each feature should be clear, specific, and supported by data
- Use Keywords/Entities vocabulary to phrase features
- Consider user context - what matters to someone buying this?
- Mix specifications with usage/benefit context where data supports it
- Modern SEO: semantic relevance and user intent over keyword stuffing

Tone:
- Simple, everyday language (like talking to an 18-year-old)
- Australian English spelling (litre, colour, organise)
- No hype or overselling
- Conversational but informative
- No excessive punctuation like em dashes

=== OUTPUT FORMAT ===

Return valid JSON only:

{{
  "description": "Product description paragraph(s), 150-300 words total",
  "key_features": [
    "Feature 1 - supported by PRODUCT DATA",
    "Feature 2 - supported by PRODUCT DATA",
    "Feature 3 - supported by PRODUCT DATA"
  ]
}}"""


@dataclass
class GeneratedDescription:
    """Result of description generation."""
    product_name: str
    price: Optional[str]
    source_text: str
    keywords_used: List[str]
    description: str
    word_count: int
    model_used: str
    products_combined: int = 1
    success: bool = True
    error: Optional[str] = None
    key_features: List[str] = field(default_factory=list)
    entities_used: bool = False
    primary_entity_path: Optional[str] = None
    supporting_entities: List[str] = None


@dataclass
class DescriptionGenerator:
    """
    Generates a single SEO-optimized product description using OpenAI ChatGPT.

    Combines data from multiple product extractions and keywords into
    one unified description.

    Attributes:
        model: OpenAI model to use
        temperature: Creativity level (0.0-1.0)
        max_tokens: Maximum tokens in response
        target_word_count: Target word count range (min, max)
        keywords_to_use: Number of keywords to include (min, max)
    """
    model: str = "gpt-4o-mini"
    temperature: float = 0.7
    max_tokens: int = 800
    target_word_count: tuple = (150, 300)
    keywords_to_use: tuple = (6, 10)
    api_key: Optional[str] = None

    _client: Any = field(default=None, repr=False, init=False)

    def __post_init__(self):
        """Initialize OpenAI client."""
        if not OPENAI_AVAILABLE:
            logger.warning("OpenAI package not installed. Install with: pip install openai")
            return

        key = self.api_key or os.getenv("OPENAI_API_KEY")
        if key:
            self._client = OpenAI(api_key=key)
            logger.info(f"OpenAI client initialized with model: {self.model}")
        else:
            logger.warning("OPENAI_API_KEY not set. Description generation will fail.")

    def _extract_text_from_product(self, product_data: Dict) -> str:
        """
        Extract relevant text from a single product.

        Args:
            product_data: Extracted product data

        Returns:
            Concatenated text from the product
        """
        parts = []

        # Add features if available
        features = product_data.get("features") or product_data.get("product_features")
        if features:
            if isinstance(features, list):
                for f in features:
                    if isinstance(f, dict):
                        # Handle feature objects with heading/description
                        heading = f.get("heading", "")
                        desc = f.get("description", "")
                        if heading and desc:
                            parts.append(f"{heading}: {desc}")
                        elif desc:
                            parts.append(desc)
                    else:
                        parts.append(str(f))
            else:
                parts.append(str(features))

        # Add additional information
        additional = product_data.get("additional_information") or product_data.get("additional_details")
        if additional:
            if isinstance(additional, dict):
                for k, v in additional.items():
                    parts.append(f"{k}: {v}")
            elif isinstance(additional, list):
                parts.extend(str(a) for a in additional)
            else:
                parts.append(str(additional))

        # Add product description if available
        description = product_data.get("product_description") or product_data.get("description")
        if description:
            parts.append(description)

        return "; ".join(parts) if parts else ""

    def _build_combined_source_text(self, products: List[Dict]) -> str:
        """
        Build combined source text from all product extractions.

        Args:
            products: List of extracted product data

        Returns:
            Combined source text from all products
        """
        all_text_parts = []

        for product in products:
            product_text = self._extract_text_from_product(product)
            if product_text:
                all_text_parts.append(product_text)

        # Combine and deduplicate key information
        combined = "\n".join(all_text_parts)

        # Truncate if too long (keep under ~2000 chars for better results)
        if len(combined) > 2000:
            combined = combined[:2000] + "..."

        return combined if combined else "No source text available."

    def _get_primary_product_name(self, products: List[Dict]) -> str:
        """
        Get the primary product name from the list of products.

        Args:
            products: List of extracted product data

        Returns:
            Primary product name (from first product with a name)
        """
        for product in products:
            name = (
                product.get("product_name") or
                product.get("title") or
                product.get("meta_title")
            )
            if name:
                return name

        return "Product"

    def _get_price_range(self, products: List[Dict]) -> Optional[str]:
        """
        Get price or price range from products.

        Args:
            products: List of extracted product data

        Returns:
            Price string or None
        """
        prices = []
        for product in products:
            price = product.get("price")
            if price:
                prices.append(price)

        if not prices:
            return None
        elif len(prices) == 1:
            return prices[0]
        else:
            # Return first price (most relevant)
            return prices[0]

    def _select_keywords(self, keywords: List[Dict], count: int = 8) -> List[str]:
        """
        Select top keywords for use in description.

        Args:
            keywords: List of keyword dicts with 'phrase' and 'importance_score'
            count: Number of keywords to select

        Returns:
            List of keyword phrases
        """
        # Sort by importance score if available
        sorted_kw = sorted(
            keywords,
            key=lambda x: x.get("importance_score", x.get("tfidf_score", 0)),
            reverse=True
        )

        # Take top N keywords
        selected = []
        for kw in sorted_kw[:count]:
            phrase = kw.get("phrase", kw.get("keyword", ""))
            if phrase and phrase not in selected:
                selected.append(phrase)

        return selected

    def generate(
        self,
        products: List[Dict],
        keywords: List[Dict],
        product_name: Optional[str] = None,
        price: Optional[str] = None,
        entities: Optional[Dict] = None,
        product_data: Optional[str] = None
    ) -> GeneratedDescription:
        """
        Generate a single SEO-optimized description from all products and keywords.

        Args:
            products: List of extracted product data to combine
            keywords: List of SEO keywords from TF-IDF analysis
            product_name: Optional override for product name
            price: Optional override for price
            entities: Optional entity analysis result with primary_entity_path and supporting_entities

        Returns:
            GeneratedDescription with the generated text
        """
        # Determine product name and price
        final_product_name = product_name or self._get_primary_product_name(products)
        final_price = price or self._get_price_range(products)

        # Track entity usage
        entities_used = False
        primary_entity_path = None
        supporting_entity_names = []

        if not OPENAI_AVAILABLE:
            return GeneratedDescription(
                product_name=final_product_name,
                price=final_price,
                source_text="",
                keywords_used=[],
                description="",
                word_count=0,
                model_used=self.model,
                products_combined=len(products),
                success=False,
                error="OpenAI package not installed. Install with: pip install openai",
                entities_used=False,
                primary_entity_path=None,
                supporting_entities=None
            )

        if not self._client:
            return GeneratedDescription(
                product_name=final_product_name,
                price=final_price,
                source_text="",
                keywords_used=[],
                description="",
                word_count=0,
                model_used=self.model,
                products_combined=len(products),
                success=False,
                error="OpenAI API key not configured. Set OPENAI_API_KEY environment variable.",
                entities_used=False,
                primary_entity_path=None,
                supporting_entities=None
            )

        # Build combined source text from all products
        source_text = self._build_combined_source_text(products)

        # Select keywords
        num_keywords = (self.keywords_to_use[0] + self.keywords_to_use[1]) // 2
        selected_keywords = self._select_keywords(keywords, num_keywords)
        keywords_list = ", ".join(selected_keywords)

        # Build entities section if entities are provided
        entities_section = ""
        if entities:
            entities_used = True
            primary_entity_path = entities.get('primary_entity_path')
            supporting = entities.get('supporting_entities', [])

            # Extract entity names
            for entity in supporting:
                name = entity.get('name', '')
                if name:
                    supporting_entity_names.append(name)

            # Build the entities section for the prompt
            entity_lines = []
            if primary_entity_path:
                entity_lines.append(f"Product Category: {primary_entity_path}")
            if supporting_entity_names:
                entity_lines.append(f"Key Attributes: {', '.join(supporting_entity_names[:8])}")

            if entity_lines:
                entities_section = "\n\nProduct Entities (incorporate these naturally):\n" + "\n".join(entity_lines) + "\n"

        # Build user prompt
        user_prompt = USER_PROMPT_TEMPLATE.format(
            product_data=product_data or "No product data provided",
            product_name=final_product_name,
            price=final_price or "N/A",
            source_text=source_text,
            keywords_list=keywords_list,
            entities_section=entities_section
        )

        try:
            # Call OpenAI API
            response = self._client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": SYSTEM_MESSAGE},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=self.temperature,
                max_tokens=self.max_tokens
            )

            # Extract and parse JSON response
            description_raw = response.choices[0].message.content.strip()

            try:
                # Handle markdown code blocks
                content = description_raw
                if content.startswith("```"):
                    content = content.split("```")[1]
                    if content.startswith("json"):
                        content = content[4:]
                    content = content.strip()

                parsed = json.loads(content)
                description = parsed.get("description", "")
                key_features = parsed.get("key_features", [])
            except (json.JSONDecodeError, KeyError):
                # Fallback: treat entire response as description
                logger.warning("Failed to parse JSON response, using raw text as description")
                description = description_raw
                key_features = []

            word_count = len(description.split())

            logger.info(f"Generated description for '{final_product_name}': {word_count} words, {len(key_features)} features (from {len(products)} products, entities_used={entities_used})")

            return GeneratedDescription(
                product_name=final_product_name,
                price=final_price,
                source_text=source_text,
                keywords_used=selected_keywords,
                description=description,
                word_count=word_count,
                model_used=self.model,
                products_combined=len(products),
                success=True,
                key_features=key_features,
                entities_used=entities_used,
                primary_entity_path=primary_entity_path,
                supporting_entities=supporting_entity_names if supporting_entity_names else None
            )

        except Exception as e:
            logger.error(f"Failed to generate description: {e}")
            return GeneratedDescription(
                product_name=final_product_name,
                price=final_price,
                source_text=source_text,
                keywords_used=selected_keywords,
                description="",
                word_count=0,
                model_used=self.model,
                products_combined=len(products),
                success=False,
                error=str(e),
                entities_used=entities_used,
                primary_entity_path=primary_entity_path,
                supporting_entities=supporting_entity_names if supporting_entity_names else None
            )


def generate_description_from_analysis(
    extraction_results: List[Dict],
    seo_phrases: List[Dict],
    product_name: Optional[str] = None,
    model: str = "gpt-4o-mini",
    api_key: Optional[str] = None
) -> GeneratedDescription:
    """
    Convenience function to generate a single description from extraction and SEO analysis results.

    Args:
        extraction_results: Results from product extraction
        seo_phrases: Phrases from SEO analysis
        product_name: Optional product name override
        model: OpenAI model to use
        api_key: Optional API key

    Returns:
        Single generated description
    """
    generator = DescriptionGenerator(model=model, api_key=api_key)
    return generator.generate(extraction_results, seo_phrases, product_name=product_name)
