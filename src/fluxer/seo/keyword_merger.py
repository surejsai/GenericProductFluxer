"""
Merge and deduplicate keywords from multiple extraction sources.

Combines TF-IDF and spaCy results into a unified SEO phrase list.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Dict, Set, Optional, Literal
import re

from .tfidf_extractor import TFIDFPhrase
from .spacy_extractor import NounPhrase
from ..logger import get_logger

logger = get_logger(__name__)


@dataclass
class SEOPhrase:
    """A merged SEO phrase from multiple extraction sources."""
    phrase: str
    doc_freq: int
    total_occurrences: int
    tfidf_score: float
    source: Literal['tfidf', 'spacy', 'both']

    # Computed importance score for ranking
    importance_score: float = 0.0

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return {
            'phrase': self.phrase,
            'doc_freq': self.doc_freq,
            'total_occurrences': self.total_occurrences,
            'tfidf_score': round(self.tfidf_score, 4),
            'source': self.source,
            'importance_score': round(self.importance_score, 4),
        }


@dataclass
class KeywordMerger:
    """
    Merge keywords from TF-IDF and spaCy extractors.

    Deduplicates and combines phrase data from both sources,
    calculating unified importance scores.
    """

    # Similarity threshold for fuzzy matching (0-1)
    similarity_threshold: float = 0.85

    # Weight factors for importance calculation
    doc_freq_weight: float = 0.4
    tfidf_weight: float = 0.35
    occurrence_weight: float = 0.25

    # Whether to normalize scores to 0-1 range
    normalize_scores: bool = True

    def merge(
        self,
        tfidf_phrases: List[TFIDFPhrase],
        spacy_phrases: List[NounPhrase],
        total_docs: int
    ) -> List[SEOPhrase]:
        """
        Merge phrases from both extraction methods.

        Args:
            tfidf_phrases: Phrases from TF-IDF extraction
            spacy_phrases: Phrases from spaCy extraction
            total_docs: Total number of documents in corpus

        Returns:
            Merged and deduplicated list of SEOPhrase objects
        """
        logger.info("Merging %d TF-IDF phrases with %d spaCy phrases",
                   len(tfidf_phrases), len(spacy_phrases))

        # Normalize phrases for matching
        merged: Dict[str, SEOPhrase] = {}

        # Process TF-IDF phrases first
        for phrase in tfidf_phrases:
            normalized = self._normalize_for_matching(phrase.phrase)
            if not normalized:
                continue

            if normalized not in merged:
                merged[normalized] = SEOPhrase(
                    phrase=phrase.phrase,
                    doc_freq=phrase.doc_freq,
                    total_occurrences=phrase.total_occurrences,
                    tfidf_score=phrase.tfidf_score,
                    source='tfidf'
                )
            else:
                # Update existing entry
                existing = merged[normalized]
                existing.doc_freq = max(existing.doc_freq, phrase.doc_freq)
                existing.total_occurrences = max(existing.total_occurrences, phrase.total_occurrences)
                existing.tfidf_score = max(existing.tfidf_score, phrase.tfidf_score)

        # Process spaCy phrases
        for phrase in spacy_phrases:
            normalized = self._normalize_for_matching(phrase.phrase)
            if not normalized:
                continue

            if normalized not in merged:
                merged[normalized] = SEOPhrase(
                    phrase=phrase.phrase,
                    doc_freq=phrase.doc_freq,
                    total_occurrences=phrase.total_occurrences,
                    tfidf_score=0.0,
                    source='spacy'
                )
            else:
                # Update existing entry - mark as 'both' sources
                existing = merged[normalized]
                existing.source = 'both'
                existing.doc_freq = max(existing.doc_freq, phrase.doc_freq)
                existing.total_occurrences = max(existing.total_occurrences, phrase.total_occurrences)

        # Also do fuzzy matching for similar phrases
        merged = self._fuzzy_deduplicate(merged)

        # Calculate importance scores
        phrases = list(merged.values())
        self._calculate_importance_scores(phrases, total_docs)

        # Sort by importance
        phrases.sort(key=lambda p: p.importance_score, reverse=True)

        logger.info("Merged into %d unique SEO phrases", len(phrases))

        return phrases

    def _normalize_for_matching(self, phrase: str) -> Optional[str]:
        """Normalize phrase for deduplication matching."""
        if not phrase:
            return None

        # Lowercase
        normalized = phrase.lower().strip()

        # Remove extra whitespace
        normalized = re.sub(r'\s+', ' ', normalized)

        # Remove trailing/leading punctuation
        normalized = re.sub(r'^[^\w]+|[^\w]+$', '', normalized)

        if len(normalized) < 2:
            return None

        return normalized

    def _fuzzy_deduplicate(self, merged: Dict[str, SEOPhrase]) -> Dict[str, SEOPhrase]:
        """
        Perform fuzzy deduplication for similar phrases.

        Merges phrases that are very similar (e.g., plural/singular variants).
        """
        # Group phrases by their root form
        root_groups: Dict[str, List[str]] = {}

        for normalized in merged.keys():
            # Get a simplified root
            root = self._get_phrase_root(normalized)
            if root not in root_groups:
                root_groups[root] = []
            root_groups[root].append(normalized)

        # Merge phrases within each group
        deduplicated: Dict[str, SEOPhrase] = {}

        for root, variants in root_groups.items():
            if len(variants) == 1:
                deduplicated[variants[0]] = merged[variants[0]]
            else:
                # Merge all variants into the best one (highest doc_freq)
                best_key = max(variants, key=lambda k: merged[k].doc_freq)
                best = merged[best_key]

                for variant in variants:
                    if variant != best_key:
                        other = merged[variant]
                        best.total_occurrences += other.total_occurrences
                        best.tfidf_score = max(best.tfidf_score, other.tfidf_score)
                        if other.source != best.source:
                            best.source = 'both'

                deduplicated[best_key] = best

        return deduplicated

    def _get_phrase_root(self, phrase: str) -> str:
        """
        Get a simplified root form for fuzzy matching.

        Handles plural/singular and common suffix variations.
        """
        words = phrase.split()
        roots = []

        for word in words:
            # Simple stemming rules
            root = word

            # Remove common plural endings
            if root.endswith('ies'):
                root = root[:-3] + 'y'
            elif root.endswith('es') and len(root) > 4:
                root = root[:-2]
            elif root.endswith('s') and not root.endswith('ss') and len(root) > 3:
                root = root[:-1]

            # Remove -ing endings
            if root.endswith('ing') and len(root) > 5:
                root = root[:-3]

            # Remove -ed endings
            if root.endswith('ed') and len(root) > 4:
                root = root[:-2]

            roots.append(root)

        return ' '.join(roots)

    def _calculate_importance_scores(
        self,
        phrases: List[SEOPhrase],
        total_docs: int
    ) -> None:
        """
        Calculate importance scores for ranking phrases.

        Combines document frequency, TF-IDF score, and total occurrences
        with configurable weights.
        """
        if not phrases:
            return

        # Find max values for normalization
        max_doc_freq = max(p.doc_freq for p in phrases) or 1
        max_tfidf = max(p.tfidf_score for p in phrases) or 1
        max_occurrences = max(p.total_occurrences for p in phrases) or 1

        for phrase in phrases:
            # Normalize individual components
            norm_doc_freq = phrase.doc_freq / max_doc_freq
            norm_tfidf = phrase.tfidf_score / max_tfidf if phrase.tfidf_score > 0 else 0
            norm_occurrences = phrase.total_occurrences / max_occurrences

            # Calculate weighted score
            score = (
                self.doc_freq_weight * norm_doc_freq +
                self.tfidf_weight * norm_tfidf +
                self.occurrence_weight * norm_occurrences
            )

            # Bonus for appearing in both sources
            if phrase.source == 'both':
                score *= 1.15

            # Scale to 0-100 for readability
            if self.normalize_scores:
                phrase.importance_score = min(score * 100, 100)
            else:
                phrase.importance_score = score


__all__ = ['KeywordMerger', 'SEOPhrase']
