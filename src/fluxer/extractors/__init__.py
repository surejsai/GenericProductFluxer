"""
Product extraction modules.

Supports two extraction backends:
- HTMLProductExtractor: ScraperAPI + custom HTML parsing
- FirecrawlProductExtractor: Firecrawl LLM-powered extraction
"""
from .html_extractor import HTMLProductExtractor, ProductData
from .firecrawl_extractor import FirecrawlProductExtractor, FirecrawlProductData

__all__ = [
    "HTMLProductExtractor",
    "ProductData",
    "FirecrawlProductExtractor",
    "FirecrawlProductData",
]
