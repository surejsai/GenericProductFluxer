from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass
from typing import Optional, List, Tuple, Dict
from html import unescape

import requests
from bs4 import BeautifulSoup, Tag

try:
    from dotenv import load_dotenv
except ModuleNotFoundError:
    def load_dotenv() -> None:
        return None

load_dotenv()

# Module logger - always logs errors, debug info controlled by LOG_LEVEL
logger = logging.getLogger(__name__)

# Ensure logger has at least one handler for standalone usage
if not logger.handlers and not logger.parent.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
    logger.addHandler(_handler)
    logger.setLevel(logging.DEBUG if os.getenv("LOG_LEVEL", "").upper() == "DEBUG" else logging.INFO)


@dataclass(slots=True)
class ProductData:
    """Extracted product information from HTML."""
    url: Optional[str] = None
    meta_title: Optional[str] = None
    meta_description: Optional[str] = None
    product_description: Optional[str] = None
    extraction_method: Optional[str] = None
    confidence_score: float = 0.0


class HTMLProductExtractor:
    """
    Extract product information using advanced NLP-based semantic matching.

    This extractor can work in two modes:
    1. URL mode: Fetches HTML via ScraperAPI and extracts product data
    2. HTML mode: Extracts from pre-fetched HTML text

    Features:
    - Advanced semantic matching and confidence scoring
    - Main product detection (filters out related/recommended products)
    - Title relevance scoring using TF-IDF-like approach
    - Structural analysis to identify primary product container
    """

    # Semantic keyword groups for product description identification
    DESCRIPTION_KEYWORDS = {
        'description': ['description', 'desc', 'describe', 'about', 'what is'],
        'details': ['details', 'detail', 'information', 'info', 'learn more'],
        'overview': ['overview', 'summary', 'introduction', 'intro'],
        'features': ['features', 'feature', 'key features', 'highlights', 'main features', 'product features'],
        'specifications': ['specifications', 'specs', 'specification', 'technical', 'tech specs'],
        'product': ['product', 'item', 'article'],
    }

    # Patterns that indicate sections to EXCLUDE (related/recommended products)
    EXCLUDE_SECTION_PATTERNS = [
        # Class/ID patterns for multi-product sections
        'related', 'similar', 'recommend', 'also-bought', 'also-viewed', 'you-may-like',
        'customers-also', 'frequently-bought', 'compare', 'alternatives', 'other-products',
        'more-products', 'product-list', 'product-grid', 'product-carousel', 'product-slider',
        'cross-sell', 'upsell', 'bundle', 'accessories', 'suggestions', 'popular',
        'trending', 'best-seller', 'new-arrival', 'featured-products', 'shop-more',
        'browse-more', 'explore-more', 'recently-viewed', 'viewed-products',
    ]

    # Text patterns that indicate multi-product sections (in headings)
    EXCLUDE_HEADING_PATTERNS = [
        'related products', 'similar products', 'you may also like', 'customers also bought',
        'frequently bought together', 'compare similar', 'other customers', 'more from',
        'shop similar', 'recommended for you', 'people also viewed', 'similar items',
        'complete the look', 'goes well with', 'pair it with', 'shop the collection',
        'more to explore', 'recently viewed', 'your browsing history', 'inspired by',
    ]

    # Weight factors for scoring sections
    WEIGHTS = {
        'exact_match': 1.0,
        'partial_match': 0.7,
        'semantic_match': 0.5,
        'container_bonus': 0.3,
        'length_factor': 0.2,
        'title_relevance': 0.4,  # Bonus for content matching product title
    }

    def __init__(
        self,
        *,
        scraperapi_key: Optional[str] = None,
        timeout_s: int = 30,
        device_type: str = "desktop",
        max_cost: str = "5",
        min_chars: int = 80,
        max_chars: int = 1200,
        debug: bool = False,
        render_js: bool = False,
        auto_retry_with_js: bool = True,
    ) -> None:
        """
        Initialize the HTML product extractor.

        Args:
            scraperapi_key: ScraperAPI key (optional, can use env var SCRAPER_API_KEY)
            timeout_s: Request timeout in seconds
            device_type: Device type for ScraperAPI ("desktop" or "mobile")
            max_cost: Maximum API cost per request (or "unlimited")
            min_chars: Minimum characters for valid description
            max_chars: Maximum characters to extract
            debug: Enable debug output
            render_js: Enable JavaScript rendering (costs more credits)
            auto_retry_with_js: Automatically retry with JS rendering if bot challenge detected
        """
        # ScraperAPI settings (optional - if not provided, can only use extract_from_html)
        self.api_key = scraperapi_key or os.getenv("SCRAPER_API_KEY")
        self.timeout_s = timeout_s
        self.device_type = device_type
        self.max_cost = max_cost
        self.render_js = render_js
        self.auto_retry_with_js = auto_retry_with_js

        # Extraction settings
        self.min_chars = min_chars
        self.max_chars = max_chars
        self.debug = debug

    def extract(self, url_or_html: str, *, is_html: bool = False) -> ProductData:
        """
        Extract product data from URL or HTML text.

        Args:
            html_or_url: Either a URL (if api_key is set) or HTML content
            url: Optional URL for reference when providing HTML directly

        Returns:
            ProductData object with extracted information
        """
        # Determine if input is URL or HTML
        input_str = (url_or_html or "").strip()
        if not input_str:
            return ProductData()

        # Check if it's a URL or HTML
        is_url_detected = input_str.startswith(('http://', 'https://', 'www.')) and not is_html

        if is_url_detected:
            # URL mode: Fetch HTML via ScraperAPI
            if not self.api_key:
                logger.error("ScraperAPI key not configured. Cannot fetch URLs. Use extract_from_html() for pre-fetched HTML or set SCRAPER_API_KEY")
                return ProductData(url=input_str)

            fetched_html = self._fetch_html_scraperapi(input_str)
            if not fetched_html:
                return ProductData(
                    url=input_str,
                    extraction_method="fetch_fail",
                    confidence_score=0.0
                )

            # Check for bot challenges
            if self._looks_like_bot_challenge(fetched_html):
                logger.warning("Detected bot challenge page for URL: %s", input_str)

                # Retry with JavaScript rendering if auto-retry is enabled and we haven't already tried
                if self.auto_retry_with_js and not self.render_js:
                    logger.info("Retrying with JavaScript rendering enabled...")

                    fetched_html_js = self._fetch_html_scraperapi(input_str, retry_with_js=True)

                    if fetched_html_js and not self._looks_like_bot_challenge(fetched_html_js):
                        logger.info("Retry with JS succeeded for URL: %s", input_str)
                        return self._extract_from_html(fetched_html_js, url=input_str)
                    else:
                        logger.warning("Retry with JS also failed for URL: %s", input_str)

                return ProductData(
                    url=input_str,
                    extraction_method="blocked",
                    confidence_score=0.0
                )

            return self._extract_from_html(fetched_html, url=input_str)

        # HTML mode: Extract from provided HTML
        return self.extract_from_html(input_str)

    def extract_from_html(self, html: str, url: Optional[str] = None) -> ProductData:
        """
        Extract product data from HTML text (no fetching).

        Args:
            html: Raw HTML content as string
            url: Optional URL for reference

        Returns:
            ProductData object with extracted information
        """
        if not html or not html.strip():
            return ProductData(url=url)

        return self._extract_from_html(html, url=url)

    def _extract_from_html(self, html: str, url: Optional[str] = None) -> ProductData:
        """Internal method to extract product data from HTML."""
        soup = BeautifulSoup(html, "html.parser")

        # Remove sections that contain related/recommended products FIRST
        self._remove_related_product_sections(soup)

        # Extract meta tags
        meta_title = self._extract_meta_title(soup)
        meta_description = self._extract_meta_description(soup)

        # Extract the main product title (H1 or og:title) for relevance matching
        product_title = self._extract_main_product_title(soup)

        logger.debug("META Title: %s...", meta_title[:50] if meta_title else 'Not found')
        logger.debug("META Description: %s...", meta_description[:50] if meta_description else 'Not found')
        logger.debug("Product Title: %s", product_title[:50] if product_title else 'Not found')

        # Try multiple extraction methods in order of reliability
        extraction_methods = [
            ('jsonld', lambda: self._extract_jsonld_product(soup, product_title)),
            ('javascript', lambda: self._extract_javascript_product(html)),
            ('main_product_section', lambda: self._extract_main_product_section(soup, product_title)),
            ('semantic_section', lambda: self._extract_semantic_section(soup, product_title)),
            ('meta_fallback', lambda: meta_description if meta_description else None),
            ('best_block', lambda: self._extract_best_block(soup, product_title)),
        ]

        for method_name, extractor_func in extraction_methods:
            try:
                description = extractor_func()
                if self._is_valid_description(description):
                    # Validate that the description is relevant to the main product
                    if product_title and not self._is_relevant_to_product(description, product_title):
                        logger.debug("EXTRACT %s content not relevant to main product, skipping", method_name)
                        continue

                    logger.debug("EXTRACT Found valid description via %s", method_name)

                    return ProductData(
                        url=url,
                        meta_title=meta_title,
                        meta_description=meta_description,
                        product_description=self._clean_and_clip(description),
                        extraction_method=method_name,
                        confidence_score=self._calculate_confidence(description, method_name),
                    )
            except Exception as e:
                logger.warning("EXTRACT %s failed: %s", method_name, e)
                continue

        logger.debug("EXTRACT No valid description found")

        return ProductData(
            url=url,
            meta_title=meta_title,
            meta_description=meta_description,
            product_description=None,
            extraction_method=None,
            confidence_score=0.0,
        )

    def _remove_related_product_sections(self, soup: BeautifulSoup) -> None:
        """Remove sections that contain related/recommended products to avoid extracting wrong content."""
        removed_count = 0

        # Find and remove elements with excluded class/id patterns
        for element in soup.find_all(['div', 'section', 'aside', 'ul', 'ol']):
            classes = ' '.join(element.get('class', []) or []).lower()
            element_id = (element.get('id') or '').lower()
            combined = f"{classes} {element_id}"

            # Check against exclusion patterns
            for pattern in self.EXCLUDE_SECTION_PATTERNS:
                if pattern in combined:
                    element.decompose()
                    removed_count += 1
                    break

        # Find and remove sections with excluded heading text
        for heading in soup.find_all(['h2', 'h3', 'h4', 'h5', 'h6']):
            heading_text = heading.get_text(' ', strip=True).lower()

            for pattern in self.EXCLUDE_HEADING_PATTERNS:
                if pattern in heading_text:
                    # Remove the heading's parent container if it's a section/div
                    parent = heading.find_parent(['section', 'div', 'aside'])
                    if parent:
                        parent.decompose()
                        removed_count += 1
                    else:
                        heading.decompose()
                    break

        # Remove product grids/carousels (multiple product cards)
        for container in soup.find_all(['div', 'section', 'ul']):
            # Count product-like cards inside
            product_cards = container.find_all(
                lambda tag: tag.name in ['div', 'li', 'article'] and
                any(p in ' '.join(tag.get('class', []) or []).lower()
                    for p in ['product', 'card', 'item', 'tile'])
            )

            # If container has multiple product cards, it's likely a product grid
            if len(product_cards) >= 3:
                # Check if this is NOT the main product area
                container_classes = ' '.join(container.get('class', []) or []).lower()
                if 'main' not in container_classes and 'primary' not in container_classes:
                    container.decompose()
                    removed_count += 1

        if removed_count > 0:
            logger.debug("FILTER Removed %d related/recommended product sections", removed_count)

    def _extract_main_product_title(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract the main product title from H1 or meta tags."""
        # Try H1 first (most reliable for main product)
        h1 = soup.find('h1')
        if h1:
            title = h1.get_text(' ', strip=True)
            # Clean up common suffixes
            title = re.sub(r'\s*[-|–]\s*.*$', '', title)  # Remove " - Brand Name" etc
            if title and len(title) >= 5:
                return title

        # Fall back to og:title or meta title
        og_title = soup.find('meta', attrs={'property': 'og:title'})
        if og_title and og_title.get('content'):
            title = og_title['content'].strip()
            title = re.sub(r'\s*[-|–]\s*.*$', '', title)
            if title:
                return title

        return self._extract_meta_title(soup)

    def _is_relevant_to_product(self, description: str, product_title: str) -> bool:
        """
        Check if the description is relevant to the main product using TF-IDF-like scoring.

        This helps filter out descriptions of related products.
        """
        if not product_title or not description:
            return True  # Can't validate, assume relevant

        # Normalize texts
        desc_lower = description.lower()
        title_lower = product_title.lower()

        # Extract significant words from title (ignore common words)
        stopwords = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
                     'of', 'with', 'by', 'from', 'is', 'are', 'was', 'were', 'be', 'been',
                     'this', 'that', 'it', 'its', 'as', 'if', 'not', 'no', 'so', 'up', 'out'}

        title_words = set(re.findall(r'\b[a-z]{3,}\b', title_lower)) - stopwords

        if not title_words:
            return True  # Can't validate

        # Count how many title words appear in description
        matches = sum(1 for word in title_words if word in desc_lower)
        match_ratio = matches / len(title_words)

        # Require at least 30% of title words to appear in description
        # This filters out descriptions that are clearly about different products
        is_relevant = match_ratio >= 0.3

        if not is_relevant:
            logger.debug("RELEVANCE Title words: %s, matches: %d/%d (%.0f%%) - NOT RELEVANT",
                        title_words, matches, len(title_words), match_ratio * 100)

        return is_relevant

    def _extract_main_product_section(self, soup: BeautifulSoup, product_title: Optional[str]) -> Optional[str]:
        """
        Find and extract content from the main product section.

        Looks for structural patterns that indicate the primary product area:
        - Proximity to price/buy button
        - Main product image area
        - Product detail containers
        """
        # Common selectors for main product sections
        main_product_selectors = [
            '[data-product-description]', '[data-description]',
            '.product-description', '.product-details', '.product-info',
            '.pdp-description', '.pdp-details', '.pdp-info',
            '#product-description', '#description', '#product-details',
            '.ProductDescription', '.ProductDetails', '.product__description',
            '[itemprop="description"]',
            '.woocommerce-product-details__short-description',
            '.product-single__description',
        ]

        for selector in main_product_selectors:
            elements = soup.select(selector)
            for element in elements:
                # Verify this element is not inside a removed section
                if element.find_parent(class_=lambda c: c and any(
                    p in ' '.join(c).lower() for p in self.EXCLUDE_SECTION_PATTERNS
                )):
                    continue

                text = self._extract_rich_text(element)
                if text and len(text) >= self.min_chars:
                    # Validate relevance to main product
                    if product_title and self._is_relevant_to_product(text, product_title):
                        logger.debug("MAIN_SECTION Found via selector: %s", selector)
                        return text

        # Look for description near price/add-to-cart button
        price_indicators = soup.find_all(
            lambda tag: tag.name in ['span', 'div', 'p'] and
            any(p in ' '.join(tag.get('class', []) or []).lower()
                for p in ['price', 'cost', 'amount'])
        )

        for price_elem in price_indicators[:3]:  # Check first 3 price elements
            # Look for description in nearby siblings or parent
            parent = price_elem.find_parent(['div', 'section', 'article'])
            if parent:
                desc_elem = parent.find(
                    lambda tag: tag.name in ['div', 'p', 'section'] and
                    any(p in ' '.join(tag.get('class', []) or []).lower()
                        for p in ['description', 'details', 'info', 'content'])
                )
                if desc_elem:
                    text = self._extract_rich_text(desc_elem)
                    if text and len(text) >= self.min_chars:
                        if not product_title or self._is_relevant_to_product(text, product_title):
                            logger.debug("MAIN_SECTION Found near price element")
                            return text

        return None

    def _extract_meta_title(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract page title from various meta sources."""
        # Priority order: title tag > og:title > twitter:title
        sources = [
            ('title', None, None),
            ('meta', 'property', 'og:title'),
            ('meta', 'name', 'twitter:title'),
            ('meta', 'property', 'twitter:title'),
        ]

        for tag_name, attr_name, attr_value in sources:
            if tag_name == 'title':
                tag = soup.find('title')
                if tag:
                    text = tag.get_text().strip()
                    if text:
                        return text
            else:
                tag = soup.find(tag_name, attrs={attr_name: attr_value})
                if tag and tag.get('content'):
                    text = tag['content'].strip()
                    if text:
                        return text

        return None

    def _extract_meta_description(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract meta description from various sources."""
        sources = [
            ('name', 'description'),
            ('property', 'og:description'),
            ('name', 'twitter:description'),
            ('property', 'twitter:description'),
        ]

        for attr_name, attr_value in sources:
            tag = soup.find('meta', attrs={attr_name: attr_value})
            if tag and tag.get('content'):
                text = tag['content'].strip()
                if text:
                    return text

        return None

    def _extract_jsonld_product(self, soup: BeautifulSoup, product_title: Optional[str] = None) -> Optional[str]:
        """
        Extract product description from JSON-LD structured data.

        Prioritizes the main product by matching against the page title.
        """
        candidates: List[Tuple[float, str, str]] = []  # (score, description, name)

        for script in soup.find_all('script', attrs={'type': 'application/ld+json'}):
            raw = (script.string or script.get_text() or '').strip()
            if not raw:
                continue

            try:
                data = json.loads(raw)
                for obj in self._iterate_jsonld(data):
                    if not isinstance(obj, dict):
                        continue

                    # Check if this is a Product type
                    obj_type = obj.get('@type', '')
                    if isinstance(obj_type, list):
                        types = {str(t).lower() for t in obj_type}
                    else:
                        types = {str(obj_type).lower()}

                    if 'product' in types:
                        desc = obj.get('description')
                        name = obj.get('name', '')

                        if isinstance(desc, str) and desc.strip():
                            desc = desc.strip()

                            # Score based on name match with page title
                            score = 1.0
                            if product_title and name:
                                name_lower = name.lower()
                                title_lower = product_title.lower()

                                # High score if names match closely
                                if name_lower == title_lower:
                                    score = 2.0
                                elif name_lower in title_lower or title_lower in name_lower:
                                    score = 1.5
                                # Check word overlap
                                else:
                                    name_words = set(name_lower.split())
                                    title_words = set(title_lower.split())
                                    overlap = len(name_words & title_words) / max(len(name_words), 1)
                                    score = 1.0 + overlap

                            candidates.append((score, desc, name))
                            logger.debug("JSON-LD Found product: %s (score=%.2f)", name[:50] if name else 'unnamed', score)

            except (json.JSONDecodeError, Exception) as e:
                logger.debug("JSON-LD parsing failed: %s", e)
                continue

        # Return the best matching product description
        if candidates:
            candidates.sort(key=lambda x: x[0], reverse=True)
            best_score, best_desc, best_name = candidates[0]
            logger.debug("JSON-LD Selected: %s (score=%.2f)", best_name[:50] if best_name else 'unnamed', best_score)
            return best_desc

        return None

    def _iterate_jsonld(self, data) -> List:
        """Recursively iterate through JSON-LD data structures."""
        if isinstance(data, dict):
            yield data
            graph = data.get('@graph')
            if isinstance(graph, list):
                for item in graph:
                    yield from self._iterate_jsonld(item)
        elif isinstance(data, list):
            for item in data:
                yield from self._iterate_jsonld(item)

    def _extract_javascript_product(self, html: str) -> Optional[str]:
        """Extract product description from JavaScript embedded data."""
        patterns = [
            r"window\.themeConfig\(['\"]product['\"],\s*({.+?})\);",
            r"var\s+product\s*=\s*({.+?});",
            r"window\.product\s*=\s*({.+?});",
            r"window\.productData\s*=\s*({.+?});",
            r"__INITIAL_STATE__\s*=\s*({.+?});",
        ]

        for pattern in patterns:
            match = re.search(pattern, html, re.DOTALL)
            if not match:
                continue

            try:
                json_str = match.group(1)
                data = json.loads(json_str)

                # Try multiple possible keys
                for key in ['description', 'content', 'body_html', 'details', 'productDescription']:
                    desc = data.get(key)
                    if isinstance(desc, str) and desc.strip():
                        # Clean HTML tags
                        desc = re.sub(r'<[^>]+>', ' ', desc)
                        desc = unescape(desc)
                        desc = re.sub(r'\s+', ' ', desc).strip()
                        if len(desc) >= self.min_chars:
                            return desc
            except (json.JSONDecodeError, KeyError, AttributeError) as e:
                logger.debug("JavaScript JSON parsing failed: %s", e)
                continue

        return None

    def _extract_semantic_section(self, soup: BeautifulSoup, product_title: Optional[str] = None) -> Optional[str]:
        """
        Use NLP-like semantic matching to find product description sections.
        Scores elements based on keyword matching and context.
        Enhanced with title relevance scoring to ensure main product content.
        """
        candidates: List[Tuple[float, str, str]] = []

        # Search through various heading tags and container elements
        heading_tags = ['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'summary', 'button', 'span', 'div', 'label', 'strong', 'p']

        for tag_name in heading_tags:
            for element in soup.find_all(tag_name):
                label = self._normalize_text(element.get_text(' ', strip=True))
                if not label or len(label) > 150:
                    continue

                # Skip if label looks like a related products heading
                if any(pattern in label for pattern in self.EXCLUDE_HEADING_PATTERNS):
                    continue

                # Calculate semantic score for this heading
                score = self._calculate_semantic_score(label)

                if score < 0.3:  # Minimum threshold
                    continue

                # Extract content near this heading
                content = self._extract_content_near_element(element)

                if content and len(content) >= self.min_chars:
                    # Check relevance to main product
                    if product_title and not self._is_relevant_to_product(content, product_title):
                        logger.debug("SEMANTIC Skipping irrelevant content from %s: %s...", tag_name, label[:30])
                        continue

                    # Add bonus based on content quality
                    length_bonus = min(0.3, len(content) / 3000.0)

                    # Add bonus for title relevance
                    title_bonus = 0.0
                    if product_title:
                        title_words = set(product_title.lower().split())
                        content_lower = content.lower()
                        matches = sum(1 for w in title_words if w in content_lower and len(w) > 3)
                        title_bonus = min(0.2, matches * 0.05)

                    final_score = score + length_bonus + title_bonus

                    candidates.append((final_score, content, tag_name))
                    logger.debug("SEMANTIC Found candidate (score=%.2f, tag=%s): %s...", final_score, tag_name, label[:50])

        # Also check for content-rich containers with specific patterns
        for container in soup.find_all(['div', 'section', 'article']):
            # Skip excluded sections
            classes = ' '.join(container.get('class', []) or []).lower()
            if any(x in classes for x in ['nav', 'footer', 'header', 'breadcrumb', 'menu', 'sidebar']):
                continue
            if any(x in classes for x in self.EXCLUDE_SECTION_PATTERNS):
                continue

            # Check if container has multiple paragraphs or strong tags
            paragraphs = container.find_all(['p', 'li'], recursive=False)
            strong_tags = container.find_all('strong')

            if len(paragraphs) >= 3 or len(strong_tags) >= 2:
                content = self._extract_rich_text(container)

                if content and len(content) >= self.min_chars:
                    # Check relevance
                    if product_title and not self._is_relevant_to_product(content, product_title):
                        continue

                    # Give bonus for structured content
                    structure_bonus = 0.1 if len(paragraphs) >= 3 else 0
                    keyword_bonus = 0.15 if 'key features' in content.lower() or 'features' in content.lower() else 0

                    score = 0.75 + structure_bonus + keyword_bonus

                    candidates.append((score, content, 'structured_container'))
                    logger.debug("SEMANTIC Found structured container (score=%.2f, paragraphs=%d, strong=%d)", score, len(paragraphs), len(strong_tags))

        # Return the best candidate
        if candidates:
            candidates.sort(key=lambda x: x[0], reverse=True)
            return candidates[0][1]

        return None

    def _calculate_semantic_score(self, text: str) -> float:
        """
        Calculate semantic similarity score for text using keyword matching.
        This is a simplified NLP approach using word overlap and semantic groups.
        """
        text = text.lower()
        max_score = 0.0

        for category, keywords in self.DESCRIPTION_KEYWORDS.items():
            for keyword in keywords:
                # Exact match
                if keyword == text:
                    max_score = max(max_score, self.WEIGHTS['exact_match'])
                # Partial match (keyword in text)
                elif keyword in text:
                    max_score = max(max_score, self.WEIGHTS['partial_match'])
                # Semantic match (word overlap)
                else:
                    overlap = self._calculate_word_overlap(text, keyword)
                    if overlap > 0.5:
                        score = self.WEIGHTS['semantic_match'] * overlap
                        max_score = max(max_score, score)

        # Additional bonus for container-like words
        container_words = ['product', 'item', 'details', 'description']
        for word in container_words:
            if word in text:
                max_score += self.WEIGHTS['container_bonus'] * 0.5

        return min(max_score, 1.0)  # Cap at 1.0

    def _calculate_word_overlap(self, text1: str, text2: str) -> float:
        """Calculate word overlap ratio between two texts."""
        words1 = set(text1.split())
        words2 = set(text2.split())

        if not words1 or not words2:
            return 0.0

        intersection = len(words1 & words2)
        union = len(words1 | words2)

        return intersection / union if union > 0 else 0.0

    def _extract_content_near_element(self, element: Tag) -> str:
        """Extract text content near a heading element."""
        # First, try the parent container (often contains all related content)
        parent = element.parent
        if parent:
            parent_text = self._extract_rich_text(parent)
            # If parent has substantial content (multiple paragraphs worth), use it
            if len(parent_text) >= 200:  # Indicates multiple paragraphs
                return parent_text

        # Try siblings (for cases where content is beside the heading)
        sibling_texts = []
        sibling = element.find_next_sibling()
        for _ in range(6):
            if sibling is None:
                break

            text = self._extract_rich_text(sibling)
            if text and len(text) >= 20:
                sibling_texts.append(text)

            sibling = sibling.find_next_sibling()

        # If we collected multiple siblings, combine them
        if sibling_texts:
            combined = ' '.join(sibling_texts)
            if len(combined) >= 40:
                return combined

        # Fallback to parent with lower threshold
        if parent:
            parent_text = self._extract_rich_text(parent)
            if len(parent_text) >= 60:
                return parent_text

        # Try next element in document
        next_elem = element.find_next()
        if next_elem:
            return self._extract_rich_text(next_elem)

        return ""

    def _extract_rich_text(self, element: Tag) -> str:
        """
        Extract text from element including tables, lists, paragraphs, etc.
        Enhanced to handle nested structures better.
        """
        parts: List[str] = []

        # Extract table data
        for table in element.find_all('table'):
            rows = []
            for tr in table.find_all('tr'):
                th = tr.find('th')
                td = tr.find('td')
                if not td:
                    continue

                key = th.get_text(' ', strip=True) if th else ''
                value = td.get_text(' ', strip=True)

                if value:
                    row_text = f"{key}: {value}".strip(': ').strip()
                    rows.append(row_text)

            if rows:
                parts.append(' | '.join(rows))

        # Extract list items (more thorough)
        for ul in element.find_all(['ul', 'ol']):
            items = [li.get_text(' ', strip=True) for li in ul.find_all('li')]
            items = [x for x in items if x]
            if items:
                parts.append(' • ' + ' • '.join(items))

        # Extract paragraphs - get ALL paragraphs within this element
        all_paragraphs = element.find_all('p')

        # Track which paragraphs we've already processed (to avoid duplicates from nesting)
        processed_texts = set()
        paragraph_texts = []

        for para in all_paragraphs:
            # Skip if it's in a list or table (already processed)
            if para.find_parent(['ul', 'ol', 'table']):
                continue

            # Get text from THIS paragraph only (not nested children)
            # Get direct text content
            para_text_parts = []
            for content in para.children:
                if isinstance(content, str):
                    para_text_parts.append(content.strip())
                elif content.name in ['strong', 'b', 'em', 'i', 'br']:
                    # Include inline formatting tags
                    para_text_parts.append(content.get_text(' ', strip=True))

            para_text = ' '.join(para_text_parts).strip()

            # Clean up excessive whitespace
            para_text = re.sub(r'\s+', ' ', para_text).strip()

            # Skip if empty, too short, or already seen
            if not para_text or len(para_text) < 10:
                continue

            para_text_lower = para_text.lower()
            if para_text_lower in processed_texts:
                continue

            processed_texts.add(para_text_lower)
            paragraph_texts.append(para_text)

        # Add paragraph texts
        if paragraph_texts:
            parts.extend(paragraph_texts)

        # If we didn't extract structured content, fall back to raw text
        if not parts:
            text = element.get_text(' ', strip=True)
            if text:
                parts.append(text)

        # Join and clean up
        result = ' '.join(parts).strip()

        # Remove excessive whitespace
        result = re.sub(r'\s+', ' ', result)

        return result

    def _extract_best_block(self, soup: BeautifulSoup, product_title: Optional[str] = None) -> Optional[str]:
        """Fallback: Find the largest relevant text block in content areas."""
        candidates: List[Tuple[int, str]] = []  # (length, text)

        # Focus on main content containers
        containers = ['article', 'main', 'section', '[role="main"]', '.product-description',
                     '.product-details', '#product-description', '#description',
                     '.product-content', '.product-body', '.item-description']

        for selector in containers:
            if selector.startswith('.') or selector.startswith('#') or selector.startswith('['):
                elements = soup.select(selector)
            else:
                elements = soup.find_all(selector)

            for element in elements:
                # Skip navigation, footer, header, and excluded sections
                classes = ' '.join(element.get('class', []) or []).lower()
                if any(x in classes for x in ['nav', 'footer', 'header', 'breadcrumb', 'menu', 'sidebar']):
                    continue
                if any(x in classes for x in self.EXCLUDE_SECTION_PATTERNS):
                    continue

                text = self._clean_text(element.get_text(' ', strip=True))

                if len(text) >= self.min_chars:
                    # Check relevance to main product
                    if product_title and not self._is_relevant_to_product(text, product_title):
                        logger.debug("BEST_BLOCK Skipping irrelevant block from %s", selector)
                        continue

                    candidates.append((len(text), text))

        # Return the longest relevant block
        if candidates:
            candidates.sort(key=lambda x: x[0], reverse=True)
            return candidates[0][1]

        return None

    def _normalize_text(self, text: str) -> str:
        """Normalize text for comparison."""
        text = (text or '').strip().lower()
        text = re.sub(r'\s+', ' ', text)
        return text

    def _clean_text(self, text: str) -> str:
        """Clean text by removing extra whitespace."""
        text = re.sub(r'\s+', ' ', (text or '')).strip()
        return text

    def _clean_and_clip(self, text: str) -> str:
        """Clean text and clip to max length."""
        text = self._clean_text(text)
        if len(text) <= self.max_chars:
            return text
        return text[:self.max_chars - 1].rstrip() + '…'

    def _is_valid_description(self, text: Optional[str]) -> bool:
        """Check if text is a valid product description."""
        if not text:
            return False

        cleaned = self._clean_text(text)
        return len(cleaned) >= self.min_chars

    def _calculate_confidence(self, description: str, method: str) -> float:
        """Calculate confidence score based on extraction method and content quality."""
        base_scores = {
            'jsonld': 0.95,
            'javascript': 0.90,
            'semantic_section': 0.85,
            'meta_fallback': 0.60,
            'best_block': 0.50,
        }

        base_score = base_scores.get(method, 0.5)

        # Adjust based on content length
        length = len(description)
        if length >= 200:
            base_score += 0.05
        if length >= 500:
            base_score += 0.05

        return min(base_score, 1.0)

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

        # Only add max_cost if it's set and not "unlimited"
        if self.max_cost and self.max_cost.lower() not in ("0", "unlimited", "none", ""):
            payload["max_cost"] = self.max_cost

        try:
            js_status = "enabled" if render == "true" else "disabled"
            logger.debug("SCRAPER Fetching: %s (device=%s, max_cost=%s, JS=%s)",
                        url, self.device_type, payload.get('max_cost', 'unlimited'), js_status)

            r = requests.get(
                "https://api.scraperapi.com/",
                params=payload,
                timeout=self.timeout_s
            )

            logger.debug("SCRAPER Response: status=%d, content-type=%s, length=%d",
                        r.status_code, r.headers.get('Content-Type', 'unknown'), len(r.text))
            for key in ['x-scraper-cost', 'x-credit-limit-remaining', 'x-credits-used']:
                if key in r.headers:
                    logger.debug("SCRAPER Header %s: %s", key, r.headers[key])

            if r.status_code != 200:
                logger.error("SCRAPER Failed with status %d for URL: %s. Response: %s",
                            r.status_code, url, r.text[:500])
                return None

            # Check if response looks like HTML
            text = r.text.strip()
            if not text:
                logger.error("SCRAPER Empty response for URL: %s", url)
                return None

            # If it starts with {, it might be JSON-wrapped
            if text.startswith('{'):
                try:
                    data = json.loads(text)
                    # Try common JSON response fields
                    html = data.get('html') or data.get('body') or data.get('content')
                    if html:
                        logger.debug("SCRAPER Extracted HTML from JSON response")
                        return html
                except json.JSONDecodeError as e:
                    logger.debug("SCRAPER Response looks like JSON but failed to parse: %s", e)

            # Otherwise treat as raw HTML
            logger.debug("SCRAPER Got raw HTML response")
            return text

        except requests.Timeout:
            logger.error("SCRAPER Timeout after %ds for URL: %s", self.timeout_s, url)
            return None
        except requests.RequestException as e:
            logger.error("SCRAPER Request error for URL %s: %s: %s", url, type(e).__name__, e)
            return None
        except Exception as e:
            logger.error("SCRAPER Unexpected error for URL %s: %s: %s", url, type(e).__name__, e, exc_info=True)
            return None

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


__all__ = ['HTMLProductExtractor', 'ProductData']
