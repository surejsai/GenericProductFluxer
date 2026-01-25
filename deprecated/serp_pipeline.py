# run_serp_pipeline.py
from __future__ import annotations

import argparse
import json
from typing import Iterable, Optional

from fluxer.search.serp_processor import AggregatedResults, SerpProcessor
from fluxer.extractors.desc_extractor import DescriptionExtractor


def run_pipeline(
    queries: Iterable[str],
    *,
    limit: int = 5,
    device: str = "desktop",
    api_key: Optional[str] = None,
    max_per_query_links: Optional[int] = None,
    timeout_s: int = 25,
    max_chars: int = 1200,
    min_chars: int = 80,
    scraperapi_key: Optional[str] = None,
    render_js: bool = True,
    country_code: str = "au",
) -> AggregatedResults:
    """
    Executes:
      1) SerpProcessor.fetch_products
      2) SerpProcessor.enrich_with_first_organic_links
      3) DescriptionExtractor.extract on each ProductHit.link (fetch via ScraperAPI)

    Returns the same AggregatedResults shape, enriched in-place.
    """

    # 1) Fetch immersive products
    aggregated = SerpProcessor.fetch_products(
        queries,
        limit=limit,
        device=device,
        api_key=api_key,
    )

    # 2) Enrich with first organic links
    aggregated = SerpProcessor.enrich_with_first_organic_links(
        aggregated,
        device=device,
        api_key=api_key,
        engine="google",
        max_per_query=max_per_query_links,
    )

    # 3) Extract descriptions from product links (ScraperAPI fetch)
    extractor = DescriptionExtractor(
        scraperapi_key=scraperapi_key,
        timeout_s=timeout_s,
        render_js=render_js,
        country_code=country_code,
        max_chars=max_chars,
        min_chars=min_chars,
    )

    for _, hits_by_title in aggregated.by_query.items():
        for _, hit in hits_by_title.items():
            if not hit.link:
                hit.description = None
                continue
            hit.description = extractor.extract(hit.link).description

    return aggregated


def _to_plain_dict(aggregated: AggregatedResults) -> dict:
    out: dict = {"by_query": {}}
    for qk, hits in aggregated.by_query.items():
        out["by_query"][qk] = {}
        for title, hit in hits.items():
            out["by_query"][qk][title] = {
                "title": hit.title,
                "price": hit.price,
                "source": hit.source,
                "link": hit.link,
                "description": getattr(hit, "description", None),
            }
    return out


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run SERP -> organic link -> description extraction pipeline (ScraperAPI fetch)."
    )
    parser.add_argument("queries", nargs="+", help="Search queries, e.g. 'range hood' 'microwave'")
    parser.add_argument("--limit", type=int, default=5, help="Max immersive products per query")
    parser.add_argument("--device", type=str, default="desktop", help="SerpApi device: mobile/desktop")
    parser.add_argument("--max-per-query-links", type=int, default=None, help="Cap organic-link enrichment per query key")

    # SerpApi
    parser.add_argument(
        "--api-key",
        type=str,
        default=None,
        help="SerpApi key override (else uses SERP_API_KEY env var)",
    )

    # Description extraction / ScraperAPI
    parser.add_argument("--timeout-s", type=int, default=25, help="HTTP timeout for description extraction")
    parser.add_argument("--min-chars", type=int, default=80, help="Minimum chars to accept a description")
    parser.add_argument("--max-chars", type=int, default=1200, help="Maximum chars to return for a description")

    parser.add_argument(
        "--scraperapi-key",
        type=str,
        default=None,
        help="ScraperAPI key override (else uses SCRAPER_API_KEY env var)",
    )
    parser.add_argument(
        "--render-js",
        action="store_true",
        help="Enable ScraperAPI JS rendering (render=true).",
    )
    parser.add_argument(
        "--no-render-js",
        dest="render_js",
        action="store_false",
        help="Disable ScraperAPI JS rendering.",
    )
    parser.set_defaults(render_js=True)

    parser.add_argument(
        "--country-code",
        type=str,
        default="au",
        help="ScraperAPI country_code (e.g. au, us, gb).",
    )

    args = parser.parse_args()

    aggregated = run_pipeline(
        args.queries,
        limit=args.limit,
        device=args.device,
        api_key=args.api_key,
        max_per_query_links=args.max_per_query_links,
        timeout_s=args.timeout_s,
        min_chars=args.min_chars,
        max_chars=args.max_chars,
        scraperapi_key=args.scraperapi_key,
        render_js=args.render_js,
        country_code=args.country_code,
    )

    print(json.dumps(_to_plain_dict(aggregated), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
