"""
Fluxer Atelier - Product Intelligence Extraction.

A modular product extraction system integrating SERP API and ScraperAPI
with advanced NLP-based semantic matching.
"""

__version__ = "1.0.0"
__author__ = "Fluxer Atelier"

from .models import ProductData, ProductHit
from .extractors.html_extractor import HTMLProductExtractor
from .search.serp_processor import SerpProcessor

__all__ = [
    "ProductData",
    "ProductHit",
    "HTMLProductExtractor",
    "SerpProcessor",
]
