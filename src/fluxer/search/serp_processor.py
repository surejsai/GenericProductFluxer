"""Utilities for fetching immersive product results from the SERP API."""
from __future__ import annotations

import logging
import os
import random
import re
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Tuple
from dotenv import load_dotenv
from serpapi import GoogleSearch

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class ProductHit:
    title: str
    price: Optional[str]
    source: Optional[str]
    link: Optional[str] = None
    description: Optional[str] = None  # <-- ADD THIS


@dataclass(slots=True)
class AggregatedResults:
    by_query: Dict[str, Dict[str, ProductHit]] = field(default_factory=dict)


class SerpProcessor:
    """Fetches immersive products for a set of queries."""

    @classmethod
    def fetch_products(
        cls,
        queries: Iterable[str],
        *,
        limit: int = 5,
        device: str = "desktop",
        api_key: Optional[str] = None,
    ) -> AggregatedResults:
        """
        Fetch immersive product results for the provided queries.

        Returns:
            AggregatedResults with nested mapping:
                by_query[query_key][title] -> ProductHit(price, source, link=None)
        """
        load_dotenv()
        key = api_key or os.getenv("SERP_API_KEY")
        if not key:
            raise ValueError("SERP API key missing. Provide api_key or set SERP_API_KEY.")
            

        aggregated = AggregatedResults()
        for query in _dedupe_preserve_order(queries):
            params = {"engine": "google", "q": query, "device": device, "api_key": key, "location": "Melbourne,Australia", "gl": "au", "hl": "en"}
            search = GoogleSearch(params)
            results = search.get_dict()

            immersive_products: List[dict] = results.get("immersive_products") or []

            # Log available result keys for debugging
            result_keys = list(results.keys())
            logger.info(f"SERP API response keys for '{query}': {result_keys}")
            logger.info(f"Found {len(immersive_products)} immersive_products for '{query}'")

            # If no immersive_products, try shopping_results as fallback
            if not immersive_products:
                shopping_results = results.get("shopping_results") or []
                logger.info(f"Trying shopping_results fallback: {len(shopping_results)} found")
                if shopping_results:
                    immersive_products = shopping_results

            per_query: Dict[str, ProductHit] = {}
            for item in immersive_products[:limit]:
                title = item.get("title")
                if not title:
                    continue
                per_query[title] = ProductHit(
                    title=title,
                    price=item.get("price"),
                    source=item.get("source"),
                    link=item.get("link"),  # Some results may already have links
                )

            query_key = _make_query_key(query, digits=5)
            aggregated.by_query[query_key] = per_query
            logger.info(f"Stored {len(per_query)} products for query '{query}'")

        return aggregated

    @classmethod
    def enrich_with_first_organic_links(
        cls,
        aggregated: AggregatedResults,
        *,
        device: str = "mobile",
        api_key: Optional[str] = None,
        engine: str = "google",
        max_per_query: Optional[int] = None,
    ) -> AggregatedResults:
        """
        Drop-in function.

        Takes output of fetch_products(), then for each ProductHit builds a query:
            "<title> <source>"
        Executes a Google search via SerpApi, reads `organic_results`,
        takes the FIRST item, and extracts `link` (key: "link").

        Mutates and returns the same AggregatedResults structure:
            by_query[query_key][title] -> ProductHit(..., link="<first organic link>")
        """
        load_dotenv()
        key = api_key or os.getenv("SERP_API_KEY")
        if not key:
            raise ValueError("SERP API key missing. Provide api_key or set SERP_API_KEY.")

        # Cache to avoid repeated searches for same (title, source) combo
        cache: Dict[Tuple[str, str], Optional[str]] = {}

        for query_key, hits_by_title in aggregated.by_query.items():
            # Optional: cap enrichment calls per query group
            items = list(hits_by_title.items())
            if max_per_query is not None:
                items = items[: max_per_query]

            for title, hit in items:
                src = (hit.source or "").strip()
                ttl = (hit.title or title or "").strip()
                if not ttl:
                    continue

                cache_key = (ttl, src)
                if cache_key in cache:
                    hit.link = cache[cache_key]
                    continue

                # Build the Google search query
                q = f"{ttl} {src}".strip()

                params = {
                    "engine": engine,   # "google" for regular Google web results
                    "q": q,
                    "device": device,
                    "api_key": key,
                }

                search = GoogleSearch(params)
                results = search.get_dict()

                organic: List[dict] = results.get("organic_results") or []
                first_link: Optional[str] = None
                if organic:
                    # SerpApi uses "link" for the URL on organic results
                    first_link = organic[0].get("link")
                    logger.debug(f"Found organic link for '{ttl[:30]}...': {first_link[:50] if first_link else 'None'}...")
                else:
                    logger.warning(f"No organic results found for query: '{q[:50]}...'")

                cache[cache_key] = first_link
                hit.link = first_link

        # Log enrichment summary
        total_hits = sum(len(hits) for hits in aggregated.by_query.values())
        hits_with_links = sum(1 for hits in aggregated.by_query.values() for h in hits.values() if h.link)
        logger.info(f"Enrichment complete: {hits_with_links}/{total_hits} products have links")

        return aggregated


__all__ = ["SerpProcessor", "ProductHit", "AggregatedResults"]


def _make_query_key(query: str, digits: int = 5) -> str:
    slug = re.sub(r"\s+", "_", query.strip().lower())
    suffix = random.randint(10 ** (digits - 1), (10 ** digits) - 1)
    return f"{slug}_{suffix}"


def _dedupe_preserve_order(queries: Iterable[str]) -> List[str]:
    seen = set()
    unique: List[str] = []
    for q in queries:
        norm = _normalize_query(q)
        if norm not in seen:
            seen.add(norm)
            unique.append(q)
    return unique


def _normalize_query(q: str) -> str:
    return " ".join(q.lower().split())
