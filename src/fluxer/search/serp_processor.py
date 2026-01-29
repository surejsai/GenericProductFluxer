"""Utilities for fetching immersive product results from the SERP API."""
from __future__ import annotations

import logging
import os
import random
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
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
        Fetch product results for the provided queries.

        Strategy:
        1. First try Google search for immersive_products
        2. If empty, check shopping_results from same response
        3. If still empty, fallback to dedicated Google Shopping API

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
            # Step 1: Try regular Google search for immersive_products
            params = {
                "engine": "google",
                "q": query,
                "device": device,
                "api_key": key,
                "location": "Australia",
                "gl": "au",
                "hl": "en"
            }
            search = GoogleSearch(params)
            results = search.get_dict()

            products: List[dict] = results.get("immersive_products") or []
            source_type = "immersive_products"

            # Log available result keys for debugging
            result_keys = list(results.keys())
            logger.info(f"SERP API response keys for '{query}': {result_keys}")
            logger.info(f"Found {len(products)} immersive_products for '{query}'")

            # Step 2: If no immersive_products, try shopping_results from same response
            if not products:
                products = results.get("shopping_results") or []
                source_type = "shopping_results (from google)"
                logger.info(f"Trying shopping_results fallback: {len(products)} found")

            # Step 3: If still no products, use dedicated Google Shopping API
            if not products:
                logger.info(f"No products from Google search, trying Google Shopping API for '{query}'")
                products = cls._fetch_from_google_shopping(query, limit, device, key)
                source_type = "google_shopping API"
                logger.info(f"Google Shopping API returned {len(products)} products")

            per_query: Dict[str, ProductHit] = {}
            for item in products[:limit]:
                title = item.get("title")
                if not title:
                    continue
                per_query[title] = ProductHit(
                    title=title,
                    price=item.get("price"),
                    source=item.get("source"),
                    link=item.get("link") or item.get("product_link"),  # google_shopping uses product_link
                )

            query_key = _make_query_key(query, digits=5)
            aggregated.by_query[query_key] = per_query
            logger.info(f"Stored {len(per_query)} products for query '{query}' (source: {source_type})")

        return aggregated

    @classmethod
    def _fetch_from_google_shopping(
        cls,
        query: str,
        limit: int,
        device: str,
        api_key: str
    ) -> List[dict]:
        """
        Fetch products from Google Shopping API as fallback.

        This is called when immersive_products and shopping_results
        from regular Google search are both empty.

        Args:
            query: Search query
            limit: Maximum products to return
            device: Device type (desktop/mobile)
            api_key: SERP API key

        Returns:
            List of product dicts with title, price, source, link fields
        """
        try:
            params = {
                "engine": "google_shopping",
                "google_domain": "google.com.au",
                "q": query,
                "hl": "en",
                "gl": "au",
                "location": "Australia",
                "device": device,
                "api_key": api_key,
            }

            search = GoogleSearch(params)
            results = search.get_dict()

            shopping_results = results.get("shopping_results") or []
            logger.info(f"Google Shopping API returned {len(shopping_results)} results for '{query}'")

            # Map google_shopping response fields to our expected format
            products = []
            for item in shopping_results[:limit]:
                products.append({
                    "title": item.get("title"),
                    "price": item.get("price"),
                    "source": item.get("source"),
                    # Google Shopping uses product_link instead of link
                    "link": item.get("link") or item.get("product_link"),
                    # Additional useful fields
                    "rating": item.get("rating"),
                    "reviews": item.get("reviews"),
                    "thumbnail": item.get("thumbnail"),
                })

            return products

        except Exception as e:
            logger.error(f"Google Shopping API call failed for '{query}': {e}")
            return []

    @classmethod
    def enrich_with_first_organic_links(
        cls,
        aggregated: AggregatedResults,
        *,
        device: str = "mobile",
        api_key: Optional[str] = None,
        engine: str = "google",
        max_per_query: Optional[int] = None,
        max_workers: int = 5,
    ) -> AggregatedResults:
        """
        Enrich products with organic search links IN PARALLEL.

        Takes output of fetch_products(), then for each ProductHit builds a query:
            "<title> <source>"
        Executes Google searches via SerpApi in parallel using ThreadPoolExecutor,
        reads `organic_results`, takes the FIRST item, and extracts `link`.

        Mutates and returns the same AggregatedResults structure:
            by_query[query_key][title] -> ProductHit(..., link="<first organic link>")
        """
        load_dotenv()
        key = api_key or os.getenv("SERP_API_KEY")
        if not key:
            raise ValueError("SERP API key missing. Provide api_key or set SERP_API_KEY.")

        # Cache to avoid repeated searches for same (title, source) combo
        cache: Dict[Tuple[str, str], Optional[str]] = {}

        # Collect all enrichment tasks
        tasks: List[Tuple[ProductHit, str, str, dict, Tuple[str, str]]] = []

        for query_key, hits_by_title in aggregated.by_query.items():
            items = list(hits_by_title.items())
            if max_per_query is not None:
                items = items[:max_per_query]

            for title, hit in items:
                # Skip if already has link (from shopping_results)
                if hit.link:
                    logger.debug(f"Skipping '{title[:30]}...' - already has link")
                    continue

                src = (hit.source or "").strip()
                ttl = (hit.title or title or "").strip()
                if not ttl:
                    continue

                cache_key = (ttl, src)
                if cache_key in cache:
                    hit.link = cache[cache_key]
                    continue

                # Build params for this search
                q = f"{ttl} {src}".strip()
                params = {
                    "engine": engine,
                    "q": q,
                    "device": device,
                    "api_key": key,
                }
                tasks.append((hit, ttl, src, params, cache_key))

        if not tasks:
            logger.info("No enrichment needed - all products have links")
            return aggregated

        logger.info(f"Enriching {len(tasks)} products in parallel (workers={max_workers})")

        def fetch_link(params: dict) -> Optional[str]:
            """Fetch single organic link."""
            try:
                search = GoogleSearch(params)
                results = search.get_dict()
                organic = results.get("organic_results") or []
                if organic:
                    return organic[0].get("link")
            except Exception as e:
                logger.warning(f"Link fetch failed: {e}")
            return None

        # Execute in parallel
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_task = {
                executor.submit(fetch_link, task[3]): task
                for task in tasks
            }

            for future in as_completed(future_to_task):
                task = future_to_task[future]
                hit, ttl, src, params, cache_key = task

                try:
                    link = future.result()
                    cache[cache_key] = link
                    hit.link = link

                    if link:
                        logger.debug(f"Found link for '{ttl[:30]}...'")
                    else:
                        logger.warning(f"No organic results for '{ttl[:30]}...'")
                except Exception as e:
                    logger.error(f"Enrichment failed for '{ttl[:30]}...': {e}")
                    cache[cache_key] = None

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
