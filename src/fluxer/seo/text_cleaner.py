"""
Text cleaning and preprocessing for SEO analysis.

Handles removal of marketing fluff, URLs, and normalization
while preserving technical terms and specifications.
"""
from __future__ import annotations

import re
from typing import List, Set, Optional
from dataclasses import dataclass, field

from ..logger import get_logger

logger = get_logger(__name__)


@dataclass
class TextCleaner:
    """
    Clean and preprocess product description text for SEO analysis.

    Removes marketing boilerplate, URLs, and noise while preserving
    technical specifications and meaningful product attributes.
    """

    # Marketing phrases to remove (case-insensitive)
    MARKETING_PHRASES: List[str] = field(default_factory=lambda: [
        # Shopping CTAs
        "buy online", "buy now", "shop now", "shop online",
        "buy online or instore", "buy online or in-store",
        "order now", "order online", "order today",
        "add to cart", "add to basket", "add to bag",
        "free shipping", "free delivery", "fast delivery",
        "limited time offer", "limited stock", "while stocks last",
        "sale ends", "hurry", "don't miss out",

        # Generic marketing
        "upgrade your", "transform your", "elevate your",
        "perfect for everyday use", "perfect for any occasion",
        "great for everyday", "ideal for everyday",
        "a must-have", "must have", "essential for",
        "best in class", "world class", "top quality",
        "premium quality", "superior quality", "exceptional quality",
        "unbeatable value", "amazing value", "great value",
        "customer favorite", "best seller", "top rated",
        "as seen on", "featured in", "recommended by",

        # Filler phrases
        "introducing the", "meet the", "discover the",
        "experience the", "enjoy the", "love the",
        "the ultimate", "the perfect", "the best",
        "designed for you", "made for you", "built for you",
        "you'll love", "you will love", "you're going to love",
        "what's included", "what you get", "package includes",
        "click here", "learn more", "find out more",
        "see details", "view details", "more info",
        "terms and conditions apply", "t&cs apply",
        "subject to availability", "while supplies last",

        # Warranty/support boilerplate
        "please contact us", "contact customer service",
        "for more information", "for assistance",
        "warranty information", "return policy",
        "satisfaction guaranteed", "money back guarantee",
    ])

    # Regex patterns to remove
    URL_PATTERN: str = r'https?://\S+|www\.\S+'
    EMAIL_PATTERN: str = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'

    # Technical terms and units to preserve
    PRESERVED_UNITS: Set[str] = field(default_factory=lambda: {
        'w', 'watt', 'watts', 'kw', 'mw',
        'v', 'volt', 'volts', 'kv', 'mv',
        'a', 'amp', 'amps', 'ma',
        'hz', 'khz', 'mhz', 'ghz',
        'l', 'litre', 'liter', 'litres', 'liters', 'ml', 'cl',
        'kg', 'g', 'gram', 'grams', 'mg', 'lb', 'lbs', 'oz',
        'mm', 'cm', 'm', 'km', 'inch', 'inches', 'ft', 'feet',
        'db', 'decibel', 'decibels',
        'rpm', 'psi', 'bar',
        'gb', 'mb', 'kb', 'tb',
        '%', 'percent', 'percentage',
        '°c', '°f', 'celsius', 'fahrenheit',
        'min', 'mins', 'minute', 'minutes',
        'sec', 'secs', 'second', 'seconds',
        'hr', 'hrs', 'hour', 'hours',
    })

    # Custom brand names to remove (configurable)
    brand_names: Set[str] = field(default_factory=set)

    def __post_init__(self) -> None:
        """Initialize compiled patterns."""
        # Compile marketing phrases pattern (case-insensitive, word boundary)
        escaped_phrases = [re.escape(phrase) for phrase in self.MARKETING_PHRASES]
        self._marketing_pattern = re.compile(
            r'\b(' + '|'.join(escaped_phrases) + r')\b',
            re.IGNORECASE
        )

        # Compile URL pattern
        self._url_pattern = re.compile(self.URL_PATTERN, re.IGNORECASE)
        self._email_pattern = re.compile(self.EMAIL_PATTERN, re.IGNORECASE)

        # Brand names pattern (compiled when brands are set)
        self._brand_pattern: Optional[re.Pattern] = None
        if self.brand_names:
            self._compile_brand_pattern()

    def _compile_brand_pattern(self) -> None:
        """Compile brand names pattern for removal."""
        if self.brand_names:
            escaped_brands = [re.escape(brand) for brand in self.brand_names]
            self._brand_pattern = re.compile(
                r'\b(' + '|'.join(escaped_brands) + r')\b',
                re.IGNORECASE
            )

    def set_brand_names(self, brands: Set[str]) -> None:
        """Set brand names to remove from text."""
        self.brand_names = brands
        self._compile_brand_pattern()

    def clean(self, text: str) -> str:
        """
        Clean text for SEO analysis.

        Args:
            text: Raw text to clean

        Returns:
            Cleaned text suitable for keyword extraction
        """
        if not text:
            return ""

        # Lowercase
        text = text.lower()

        # Remove URLs
        text = self._url_pattern.sub(' ', text)

        # Remove emails
        text = self._email_pattern.sub(' ', text)

        # Remove marketing phrases
        text = self._marketing_pattern.sub(' ', text)

        # Remove brand names if configured
        if self._brand_pattern:
            text = self._brand_pattern.sub(' ', text)

        # Remove HTML entities
        text = re.sub(r'&[a-z]+;|&#\d+;', ' ', text)

        # Normalize dashes and special chars (but keep hyphens in compound words)
        text = re.sub(r'[–—]', '-', text)

        # Remove excessive punctuation (keep . , - for compound terms)
        text = re.sub(r'[^\w\s.,\-°%]', ' ', text)

        # Normalize whitespace
        text = re.sub(r'\s+', ' ', text)

        # Remove standalone single characters (except units)
        words = text.split()
        cleaned_words = []
        for word in words:
            # Keep if length > 1 or if it's a recognized unit
            if len(word) > 1 or word.lower() in self.PRESERVED_UNITS:
                cleaned_words.append(word)

        text = ' '.join(cleaned_words)

        return text.strip()

    def extract_product_text(self, product: dict) -> str:
        """
        Extract all description text from a product object.

        Concatenates features, headings, descriptions, and additional info.

        Args:
            product: Product dict with Firecrawl schema

        Returns:
            Combined text from all description fields
        """
        parts = []

        # Extract from features
        features = product.get('features') or []
        for feature in features:
            if isinstance(feature, dict):
                heading = feature.get('heading', '')
                description = feature.get('description', '')
                if heading:
                    parts.append(heading)
                if description:
                    parts.append(description)
            elif isinstance(feature, str):
                parts.append(feature)

        # Extract additional information
        additional_info = product.get('additional_information')
        if additional_info:
            parts.append(additional_info)

        # Optionally include product name for context
        product_name = product.get('product_name')
        if product_name:
            parts.insert(0, product_name)

        return ' '.join(parts)

    def build_corpus(self, products: List[dict]) -> List[str]:
        """
        Build a cleaned text corpus from product list.

        Args:
            products: List of product dicts

        Returns:
            List of cleaned document strings (one per product)
        """
        corpus = []

        for i, product in enumerate(products):
            raw_text = self.extract_product_text(product)
            cleaned_text = self.clean(raw_text)

            if cleaned_text:
                corpus.append(cleaned_text)
            else:
                logger.debug("Product %d produced empty text after cleaning", i)

        logger.info("Built corpus with %d documents from %d products",
                   len(corpus), len(products))

        return corpus


__all__ = ['TextCleaner']
