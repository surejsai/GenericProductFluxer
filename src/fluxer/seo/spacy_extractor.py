"""
spaCy-based noun phrase extraction.

Uses spaCy NLP for extracting meaningful noun chunks
from product descriptions.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Dict, Set, Optional
from collections import Counter
import re

from ..logger import get_logger

logger = get_logger(__name__)

# Lazy import spacy to handle missing dependency gracefully
_spacy_available = None
_nlp = None


def _check_spacy() -> bool:
    """Check if spacy is available and load the model."""
    global _spacy_available, _nlp

    if _spacy_available is not None:
        return _spacy_available

    try:
        import spacy

        # Try to load English model
        try:
            _nlp = spacy.load("en_core_web_sm")
            _spacy_available = True
            logger.debug("spaCy with en_core_web_sm model loaded")
        except OSError:
            # Model not installed, try to download it
            logger.warning("spaCy model not found, attempting to download...")
            try:
                from spacy.cli import download
                download("en_core_web_sm")
                _nlp = spacy.load("en_core_web_sm")
                _spacy_available = True
            except Exception as e:
                logger.warning("Could not download spaCy model: %s", e)
                _spacy_available = False

    except ImportError:
        _spacy_available = False
        logger.warning("spaCy not installed. Noun phrase extraction will use fallback.")

    return _spacy_available


@dataclass
class NounPhrase:
    """A noun phrase extracted via spaCy."""
    phrase: str
    doc_freq: int
    total_occurrences: int
    root_word: Optional[str] = None


@dataclass
class SpacyExtractor:
    """
    Extract noun phrases using spaCy NLP.

    Identifies meaningful noun chunks from product descriptions
    and normalizes them for SEO analysis.
    """

    # Minimum phrase length (characters)
    min_length: int = 3

    # Maximum phrase length (words)
    max_words: int = 5

    # Minimum document frequency
    min_df: int = 2

    # Top N phrases to return
    top_n: int = 300

    # Stopwords to strip from phrase edges
    edge_stopwords: Set[str] = field(default_factory=lambda: {
        'the', 'a', 'an', 'this', 'that', 'these', 'those',
        'its', 'their', 'our', 'your', 'my', 'his', 'her',
        'some', 'any', 'all', 'each', 'every', 'both', 'few',
        'more', 'most', 'other', 'another', 'such', 'no',
        'many', 'much', 'several', 'various', 'certain',
        'new', 'old', 'good', 'great', 'best', 'better',
        'first', 'last', 'next', 'previous', 'same', 'different',
    })

    # Patterns to skip entirely
    skip_patterns: List[str] = field(default_factory=lambda: [
        r'^\d+$',  # Pure numbers
        r'^[^\w\s]+$',  # Pure punctuation
        r'^(it|they|we|you|i|he|she)$',  # Pronouns
    ])

    def __post_init__(self) -> None:
        """Initialize compiled patterns."""
        self._skip_patterns = [re.compile(p, re.IGNORECASE) for p in self.skip_patterns]

    def extract(self, corpus: List[str]) -> List[NounPhrase]:
        """
        Extract noun phrases from corpus.

        Args:
            corpus: List of cleaned document strings

        Returns:
            List of NounPhrase objects sorted by frequency
        """
        if not corpus:
            logger.warning("Empty corpus provided to spaCy extractor")
            return []

        if _check_spacy():
            return self._spacy_extract(corpus)
        else:
            return self._fallback_extract(corpus)

    def _spacy_extract(self, corpus: List[str]) -> List[NounPhrase]:
        """Extract noun phrases using spaCy."""
        logger.info("Starting spaCy noun phrase extraction on %d documents", len(corpus))

        phrase_counts: Counter = Counter()
        phrase_docs: Dict[str, Set[int]] = {}
        phrase_roots: Dict[str, str] = {}

        # Process documents in batches for efficiency
        batch_size = 100
        for batch_start in range(0, len(corpus), batch_size):
            batch = corpus[batch_start:batch_start + batch_size]

            # Process batch with spaCy
            for doc_idx, doc in enumerate(_nlp.pipe(batch, disable=['ner'])):
                actual_idx = batch_start + doc_idx

                # Extract noun chunks
                for chunk in doc.noun_chunks:
                    # Normalize the phrase
                    normalized = self._normalize_phrase(chunk.text)

                    if not normalized:
                        continue

                    # Skip if matches skip patterns
                    if any(p.match(normalized) for p in self._skip_patterns):
                        continue

                    # Skip if too short or too long
                    word_count = len(normalized.split())
                    if len(normalized) < self.min_length or word_count > self.max_words:
                        continue

                    # Count occurrences
                    phrase_counts[normalized] += 1

                    # Track document frequency
                    if normalized not in phrase_docs:
                        phrase_docs[normalized] = set()
                    phrase_docs[normalized].add(actual_idx)

                    # Store root word
                    if normalized not in phrase_roots:
                        phrase_roots[normalized] = chunk.root.text.lower()

        # Convert to NounPhrase objects
        phrases = []
        for phrase_text, count in phrase_counts.items():
            doc_freq = len(phrase_docs.get(phrase_text, set()))

            if doc_freq >= self.min_df:
                phrases.append(NounPhrase(
                    phrase=phrase_text,
                    doc_freq=doc_freq,
                    total_occurrences=count,
                    root_word=phrase_roots.get(phrase_text)
                ))

        # Sort by document frequency, then by total occurrences
        phrases.sort(key=lambda p: (p.doc_freq, p.total_occurrences), reverse=True)

        result = phrases[:self.top_n]
        logger.info("spaCy extracted %d noun phrases", len(result))

        return result

    def _normalize_phrase(self, phrase: str) -> Optional[str]:
        """
        Normalize a noun phrase for comparison.

        - Lowercase
        - Strip edge stopwords
        - Collapse whitespace
        """
        if not phrase:
            return None

        # Lowercase and strip
        normalized = phrase.lower().strip()

        # Remove punctuation from edges
        normalized = re.sub(r'^[^\w]+|[^\w]+$', '', normalized)

        # Collapse whitespace
        normalized = re.sub(r'\s+', ' ', normalized)

        # Strip edge stopwords
        words = normalized.split()
        while words and words[0] in self.edge_stopwords:
            words.pop(0)
        while words and words[-1] in self.edge_stopwords:
            words.pop()

        if not words:
            return None

        return ' '.join(words)

    def _fallback_extract(self, corpus: List[str]) -> List[NounPhrase]:
        """
        Fallback noun phrase extraction without spaCy.

        Uses simple heuristics to identify potential noun phrases.
        """
        logger.info("Using fallback noun phrase extraction")

        # Common adjective patterns that often precede nouns
        adjective_patterns = {
            'digital', 'automatic', 'electric', 'electronic', 'wireless',
            'compact', 'portable', 'adjustable', 'removable', 'built-in',
            'stainless', 'steel', 'glass', 'plastic', 'metal', 'aluminum',
            'led', 'lcd', 'touch', 'smart', 'high', 'low', 'fast', 'slow',
            'large', 'small', 'medium', 'mini', 'micro', 'dual', 'triple',
            'multi', 'single', 'double', 'full', 'half', 'auto', 'manual',
            'front', 'back', 'side', 'top', 'bottom', 'inner', 'outer',
            'easy', 'quick', 'safe', 'secure', 'quiet', 'silent', 'powerful',
        }

        # Common technical noun suffixes
        noun_suffixes = {
            'tion', 'sion', 'ment', 'ness', 'ity', 'ance', 'ence',
            'er', 'or', 'ist', 'ism', 'ing', 'age', 'ure', 'ry',
            'ty', 'al', 'ics', 'ogy', 'logy',
        }

        phrase_counts: Counter = Counter()
        phrase_docs: Dict[str, Set[int]] = {}

        for doc_idx, doc in enumerate(corpus):
            words = doc.lower().split()

            # Extract potential noun phrases (adj + noun, noun + noun combinations)
            for i, word in enumerate(words):
                # Single important words
                if len(word) >= 4 and any(word.endswith(s) for s in noun_suffixes):
                    phrase_counts[word] += 1
                    if word not in phrase_docs:
                        phrase_docs[word] = set()
                    phrase_docs[word].add(doc_idx)

                # Two-word phrases
                if i < len(words) - 1:
                    next_word = words[i + 1]

                    # adjective + noun pattern
                    if (word in adjective_patterns or
                            any(next_word.endswith(s) for s in noun_suffixes)):
                        phrase = f"{word} {next_word}"
                        if len(phrase) >= self.min_length:
                            phrase_counts[phrase] += 1
                            if phrase not in phrase_docs:
                                phrase_docs[phrase] = set()
                            phrase_docs[phrase].add(doc_idx)

                    # noun + noun pattern
                    if (any(word.endswith(s) for s in noun_suffixes) and
                            any(next_word.endswith(s) for s in noun_suffixes)):
                        phrase = f"{word} {next_word}"
                        if len(phrase) >= self.min_length:
                            phrase_counts[phrase] += 1
                            if phrase not in phrase_docs:
                                phrase_docs[phrase] = set()
                            phrase_docs[phrase].add(doc_idx)

        # Convert to NounPhrase objects
        phrases = []
        for phrase_text, count in phrase_counts.items():
            doc_freq = len(phrase_docs.get(phrase_text, set()))

            if doc_freq >= self.min_df:
                phrases.append(NounPhrase(
                    phrase=phrase_text,
                    doc_freq=doc_freq,
                    total_occurrences=count,
                    root_word=phrase_text.split()[-1] if phrase_text else None
                ))

        # Sort and return
        phrases.sort(key=lambda p: (p.doc_freq, p.total_occurrences), reverse=True)

        return phrases[:self.top_n]


__all__ = ['SpacyExtractor', 'NounPhrase']
