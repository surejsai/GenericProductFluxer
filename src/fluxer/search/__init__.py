"""
Search and product discovery modules.
"""
from .serp_processor import SerpProcessor, ProductHit

# AggregatedProducts is now in models.py
from ..models import AggregatedProducts

__all__ = ["SerpProcessor", "ProductHit", "AggregatedProducts"]
