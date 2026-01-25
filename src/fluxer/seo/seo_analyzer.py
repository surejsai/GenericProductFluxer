"""
Main SEO analyzer that orchestrates keyword extraction.

Provides a unified interface for analyzing product descriptions
and generating SEO phrase recommendations.
"""
from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field
from typing import List, Dict, Set, Optional, Any
from datetime import datetime

from .text_cleaner import TextCleaner
from .tfidf_extractor import TFIDFExtractor
from .spacy_extractor import SpacyExtractor
from .keyword_merger import KeywordMerger, SEOPhrase
from ..logger import get_logger

logger = get_logger(__name__)


@dataclass
class SEOAnalysisResult:
    """Result of SEO analysis on product descriptions."""
    phrases: List[SEOPhrase]
    total_products: int
    total_documents: int  # Products with non-empty descriptions
    analysis_timestamp: str
    config: Dict[str, Any]

    # Statistics
    unique_phrases: int = 0
    phrases_from_tfidf: int = 0
    phrases_from_spacy: int = 0
    phrases_from_both: int = 0

    def __post_init__(self):
        """Calculate statistics."""
        self.unique_phrases = len(self.phrases)
        self.phrases_from_tfidf = sum(1 for p in self.phrases if p.source == 'tfidf')
        self.phrases_from_spacy = sum(1 for p in self.phrases if p.source == 'spacy')
        self.phrases_from_both = sum(1 for p in self.phrases if p.source == 'both')

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'phrases': [p.to_dict() for p in self.phrases],
            'statistics': {
                'total_products': self.total_products,
                'total_documents': self.total_documents,
                'unique_phrases': self.unique_phrases,
                'phrases_from_tfidf': self.phrases_from_tfidf,
                'phrases_from_spacy': self.phrases_from_spacy,
                'phrases_from_both': self.phrases_from_both,
            },
            'analysis_timestamp': self.analysis_timestamp,
            'config': self.config,
        }

    def to_csv(self) -> str:
        """Generate CSV content for export."""
        output = io.StringIO()
        writer = csv.writer(output)

        # Header
        writer.writerow([
            'phrase',
            'doc_freq',
            'total_occurrences',
            'tfidf_score',
            'importance_score',
            'source'
        ])

        # Data rows
        for phrase in self.phrases:
            writer.writerow([
                phrase.phrase,
                phrase.doc_freq,
                phrase.total_occurrences,
                round(phrase.tfidf_score, 4),
                round(phrase.importance_score, 2),
                phrase.source
            ])

        return output.getvalue()

    def get_top_phrases(self, n: int = 50) -> List[Dict]:
        """Get top N phrases as dictionaries."""
        return [p.to_dict() for p in self.phrases[:n]]

    def get_category_breakdown(self) -> Dict[str, List[Dict]]:
        """
        Categorize phrases by their importance level.

        Returns phrases grouped as high, medium, low importance.
        """
        high = []
        medium = []
        low = []

        for phrase in self.phrases:
            phrase_dict = phrase.to_dict()
            if phrase.importance_score >= 70:
                high.append(phrase_dict)
            elif phrase.importance_score >= 40:
                medium.append(phrase_dict)
            else:
                low.append(phrase_dict)

        return {
            'high_importance': high[:100],
            'medium_importance': medium[:100],
            'low_importance': low[:100],
        }


@dataclass
class SEOAnalyzer:
    """
    Main SEO analyzer for product descriptions.

    Orchestrates text cleaning, keyword extraction, and result generation.
    """

    # Configuration
    top_n_phrases: int = 500
    min_doc_freq: int = 2
    ngram_range: tuple = (1, 3)

    # Brand names to exclude (optional)
    brand_names: Set[str] = field(default_factory=set)

    # Component instances
    _text_cleaner: Optional[TextCleaner] = field(default=None, repr=False)
    _tfidf_extractor: Optional[TFIDFExtractor] = field(default=None, repr=False)
    _spacy_extractor: Optional[SpacyExtractor] = field(default=None, repr=False)
    _keyword_merger: Optional[KeywordMerger] = field(default=None, repr=False)

    def __post_init__(self) -> None:
        """Initialize component instances."""
        self._text_cleaner = TextCleaner(brand_names=self.brand_names)
        self._tfidf_extractor = TFIDFExtractor(
            ngram_range=self.ngram_range,
            min_df=self.min_doc_freq,
            top_n=self.top_n_phrases
        )
        self._spacy_extractor = SpacyExtractor(
            min_df=self.min_doc_freq,
            top_n=self.top_n_phrases
        )
        self._keyword_merger = KeywordMerger()

    def analyze(self, products: List[Dict[str, Any]]) -> SEOAnalysisResult:
        """
        Perform SEO analysis on product descriptions.

        Args:
            products: List of product dictionaries with Firecrawl schema

        Returns:
            SEOAnalysisResult with extracted phrases and statistics
        """
        logger.info("Starting SEO analysis on %d products", len(products))

        # Step 1: Build corpus
        corpus = self._text_cleaner.build_corpus(products)

        if not corpus:
            logger.warning("No valid documents in corpus after cleaning")
            return SEOAnalysisResult(
                phrases=[],
                total_products=len(products),
                total_documents=0,
                analysis_timestamp=datetime.utcnow().isoformat(),
                config=self._get_config()
            )

        logger.info("Built corpus with %d documents", len(corpus))

        # Step 2: TF-IDF extraction
        tfidf_phrases = self._tfidf_extractor.extract(corpus)
        logger.info("TF-IDF extracted %d phrases", len(tfidf_phrases))

        # Step 3: spaCy extraction
        spacy_phrases = self._spacy_extractor.extract(corpus)
        logger.info("spaCy extracted %d phrases", len(spacy_phrases))

        # Step 4: Merge results
        merged_phrases = self._keyword_merger.merge(
            tfidf_phrases,
            spacy_phrases,
            total_docs=len(corpus)
        )

        # Limit to top N
        merged_phrases = merged_phrases[:self.top_n_phrases]

        logger.info("SEO analysis complete: %d unique phrases", len(merged_phrases))

        return SEOAnalysisResult(
            phrases=merged_phrases,
            total_products=len(products),
            total_documents=len(corpus),
            analysis_timestamp=datetime.utcnow().isoformat(),
            config=self._get_config()
        )

    def analyze_from_extraction_results(
        self,
        extraction_results: List[Dict[str, Any]]
    ) -> SEOAnalysisResult:
        """
        Analyze SEO from batch extraction results.

        Extracts product data from the extraction result format
        and performs analysis.

        Args:
            extraction_results: Results from /api/extract-batch endpoint

        Returns:
            SEOAnalysisResult with extracted phrases
        """
        # Convert extraction results to product format
        products = []

        for result in extraction_results:
            if result.get('error'):
                continue

            product = {
                'product_name': result.get('product_name') or result.get('title'),
                'price': result.get('price'),
                'features': result.get('features') or [],
                'additional_information': result.get('additional_information'),
            }

            # If no features but has product_description, parse it
            if not product['features'] and result.get('product_description'):
                # Split description into feature-like structures
                description = result['product_description']
                parts = description.split('. ')
                product['features'] = [
                    {'heading': '', 'description': part}
                    for part in parts if len(part) > 10
                ]

            products.append(product)

        return self.analyze(products)

    def _get_config(self) -> Dict[str, Any]:
        """Get current configuration as dictionary."""
        return {
            'top_n_phrases': self.top_n_phrases,
            'min_doc_freq': self.min_doc_freq,
            'ngram_range': list(self.ngram_range),
            'brand_names_count': len(self.brand_names),
        }


__all__ = ['SEOAnalyzer', 'SEOAnalysisResult']
