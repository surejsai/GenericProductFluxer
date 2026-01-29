"""
TF-IDF based keyword and phrase extraction.

Uses scikit-learn's TfidfVectorizer for statistical keyword extraction
with configurable n-gram ranges and frequency thresholds.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional
import numpy as np

from ..logger import get_logger

logger = get_logger(__name__)

# Lazy import sklearn to handle missing dependency gracefully
_sklearn_available = None
TfidfVectorizer = None


def _check_sklearn() -> bool:
    """Check if sklearn is available and import it."""
    global _sklearn_available, TfidfVectorizer

    if _sklearn_available is not None:
        return _sklearn_available

    try:
        from sklearn.feature_extraction.text import TfidfVectorizer as _TfidfVectorizer
        TfidfVectorizer = _TfidfVectorizer
        _sklearn_available = True
        logger.debug("scikit-learn is available")
    except ImportError:
        _sklearn_available = False
        logger.warning("scikit-learn not installed. TF-IDF extraction will be limited.")

    return _sklearn_available


@dataclass
class TFIDFPhrase:
    """A phrase extracted via TF-IDF analysis."""
    phrase: str
    tfidf_score: float
    doc_freq: int
    total_occurrences: int


@dataclass
class TFIDFExtractor:
    """
    Extract keywords and phrases using TF-IDF analysis.

    Uses scikit-learn's TfidfVectorizer to identify statistically
    significant phrases across a corpus of product descriptions.
    """

    # N-gram range (1=unigrams, 2=bigrams, 3=trigrams)
    ngram_range: Tuple[int, int] = (1, 3)

    # Minimum document frequency (phrase must appear in at least this many docs)
    min_df: int = 2

    # Maximum document frequency ratio (ignore terms in more than X% of docs)
    max_df: float = 0.85

    # Maximum number of features to extract
    max_features: int = 5000

    # Top N phrases to return (200 is practical for SEO)
    top_n: int = 200

    # Additional stopwords beyond English defaults
    extra_stopwords: List[str] = field(default_factory=lambda: [
        'product', 'products', 'item', 'items', 'feature', 'features',
        'includes', 'including', 'included', 'include',
        'provides', 'providing', 'provided', 'provide',
        'offers', 'offering', 'offered', 'offer',
        'available', 'availability',
        'new', 'latest', 'model', 'version', 'series',
        'use', 'uses', 'using', 'used',
        'make', 'makes', 'making', 'made',
        'help', 'helps', 'helping', 'helped',
        'allow', 'allows', 'allowing', 'allowed',
        'enable', 'enables', 'enabling', 'enabled',
        'ensure', 'ensures', 'ensuring', 'ensured',
        'provide', 'provides', 'providing', 'provided',
        'also', 'just', 'even', 'really', 'very', 'well',
        'like', 'way', 'thing', 'things', 'lot', 'lots',
        'need', 'needs', 'want', 'wants',
        'come', 'comes', 'coming', 'came',
        'get', 'gets', 'getting', 'got',
        'see', 'look', 'looks', 'looking',
        'know', 'knows', 'knowing', 'known',
    ])

    def __post_init__(self) -> None:
        """Initialize the vectorizer."""
        self._vectorizer = None
        self._feature_names = None
        self._tfidf_matrix = None

    def extract(self, corpus: List[str]) -> List[TFIDFPhrase]:
        """
        Extract top phrases from corpus using TF-IDF.

        Args:
            corpus: List of cleaned document strings

        Returns:
            List of TFIDFPhrase objects sorted by importance
        """
        if not corpus:
            logger.warning("Empty corpus provided to TF-IDF extractor")
            return []

        if not _check_sklearn():
            logger.error("scikit-learn not available, cannot perform TF-IDF extraction")
            return self._fallback_extraction(corpus)

        try:
            return self._sklearn_extract(corpus)
        except Exception as e:
            logger.error("TF-IDF extraction failed: %s", e, exc_info=True)
            return self._fallback_extraction(corpus)

    def _sklearn_extract(self, corpus: List[str]) -> List[TFIDFPhrase]:
        """Perform TF-IDF extraction using scikit-learn."""
        logger.info("Starting TF-IDF extraction on %d documents", len(corpus))

        # Build combined stopwords list
        stopwords = list(self.extra_stopwords)

        # Initialize vectorizer
        self._vectorizer = TfidfVectorizer(
            ngram_range=self.ngram_range,
            stop_words='english',
            min_df=self.min_df,
            max_df=self.max_df,
            max_features=self.max_features,
            lowercase=True,
            token_pattern=r'(?u)\b[a-zA-Z][a-zA-Z0-9\-]*[a-zA-Z0-9]\b|\b[a-zA-Z]\b'
        )

        # Fit and transform
        self._tfidf_matrix = self._vectorizer.fit_transform(corpus)
        self._feature_names = self._vectorizer.get_feature_names_out()

        logger.info("TF-IDF extracted %d unique features", len(self._feature_names))

        # Calculate aggregate scores
        phrases = self._calculate_phrase_scores(corpus)

        # Filter extra stopwords
        stopwords_set = set(stopwords)
        filtered_phrases = []
        for phrase in phrases:
            # Skip if phrase is just a stopword or contains only stopwords
            words = phrase.phrase.split()
            if all(w in stopwords_set for w in words):
                continue
            # Skip very short phrases
            if len(phrase.phrase) < 3:
                continue
            filtered_phrases.append(phrase)

        # Sort by combined score (doc_freq * tfidf_score) and return top N
        filtered_phrases.sort(
            key=lambda p: (p.doc_freq, p.tfidf_score),
            reverse=True
        )

        result = filtered_phrases[:self.top_n]
        logger.info("TF-IDF returning %d top phrases", len(result))

        return result

    def _calculate_phrase_scores(self, corpus: List[str]) -> List[TFIDFPhrase]:
        """Calculate aggregate TF-IDF scores and frequencies for each phrase."""
        phrases = []

        # Get the TF-IDF matrix as array
        tfidf_array = self._tfidf_matrix.toarray()

        for idx, feature in enumerate(self._feature_names):
            # Column for this feature
            col = tfidf_array[:, idx]

            # TF-IDF score = sum across all documents
            tfidf_score = float(np.sum(col))

            # Document frequency = number of docs where this phrase appears
            doc_freq = int(np.sum(col > 0))

            # Total occurrences (approximate from inverse document frequency)
            # We'll count actual occurrences for more accuracy
            total_occurrences = sum(
                doc.lower().count(feature.lower())
                for doc in corpus
            )

            if doc_freq > 0:
                phrases.append(TFIDFPhrase(
                    phrase=feature,
                    tfidf_score=round(tfidf_score, 4),
                    doc_freq=doc_freq,
                    total_occurrences=total_occurrences
                ))

        return phrases

    def _fallback_extraction(self, corpus: List[str]) -> List[TFIDFPhrase]:
        """
        Simple frequency-based extraction when sklearn is unavailable.

        Falls back to basic word counting with n-gram support.
        """
        logger.info("Using fallback frequency extraction")

        from collections import Counter

        # English stopwords (minimal set)
        stopwords = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
            'of', 'with', 'by', 'from', 'is', 'are', 'was', 'were', 'be', 'been',
            'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would',
            'could', 'should', 'may', 'might', 'must', 'shall', 'can', 'this',
            'that', 'these', 'those', 'it', 'its', 'as', 'if', 'when', 'than',
            'so', 'no', 'not', 'only', 'same', 'such', 'too', 'very', 'just',
            'also', 'now', 'here', 'there', 'where', 'which', 'who', 'what',
            'all', 'each', 'every', 'both', 'few', 'more', 'most', 'other',
            'some', 'any', 'no', 'nor', 'own', 'out', 'up', 'down', 'off', 'over',
            'under', 'again', 'further', 'then', 'once', 'your', 'our', 'their',
            'we', 'you', 'he', 'she', 'they', 'i', 'me', 'him', 'her', 'us', 'them',
        }
        stopwords.update(self.extra_stopwords)

        # Count n-grams
        ngram_counts: Counter = Counter()
        doc_freqs: Dict[str, set] = {}

        for doc_idx, doc in enumerate(corpus):
            words = doc.lower().split()

            # Generate n-grams
            for n in range(self.ngram_range[0], self.ngram_range[1] + 1):
                for i in range(len(words) - n + 1):
                    ngram_words = words[i:i + n]

                    # Skip if all words are stopwords
                    if all(w in stopwords for w in ngram_words):
                        continue

                    ngram = ' '.join(ngram_words)

                    ngram_counts[ngram] += 1

                    if ngram not in doc_freqs:
                        doc_freqs[ngram] = set()
                    doc_freqs[ngram].add(doc_idx)

        # Convert to phrases
        phrases = []
        for ngram, count in ngram_counts.items():
            doc_freq = len(doc_freqs.get(ngram, set()))

            if doc_freq >= self.min_df:
                # Simple TF-IDF approximation
                idf = np.log(len(corpus) / (doc_freq + 1)) + 1
                tfidf_score = count * idf

                phrases.append(TFIDFPhrase(
                    phrase=ngram,
                    tfidf_score=round(tfidf_score, 4),
                    doc_freq=doc_freq,
                    total_occurrences=count
                ))

        # Sort and return top N
        phrases.sort(key=lambda p: (p.doc_freq, p.tfidf_score), reverse=True)

        return phrases[:self.top_n]


__all__ = ['TFIDFExtractor', 'TFIDFPhrase']
