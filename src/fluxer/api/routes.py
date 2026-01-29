"""
API routes for Fluxer application.
"""
from concurrent.futures import ThreadPoolExecutor, as_completed
from flask import Blueprint, request, jsonify, Response
from typing import Dict, Any, Optional, Union

from ..extractors.html_extractor import HTMLProductExtractor
from ..extractors.firecrawl_extractor import FirecrawlProductExtractor
from ..search.serp_processor import SerpProcessor
from ..seo.seo_analyzer import SEOAnalyzer
from ..seo.description_generator import DescriptionGenerator
from ..seo.entity_extractor import EntityExtractor
from ..config import Config
from ..logger import get_logger

logger = get_logger(__name__)

# Create blueprint
api_bp = Blueprint('api', __name__, url_prefix='/api')


def get_extractor() -> Union[HTMLProductExtractor, FirecrawlProductExtractor]:
    """Get the appropriate extractor based on configuration."""
    if Config.EXTRACTOR_TYPE == "firecrawl":
        logger.debug("Using Firecrawl extractor")
        return FirecrawlProductExtractor(
            timeout_s=45,  # Reduced timeout for faster failure
        )
    else:
        logger.debug("Using HTML extractor")
        return HTMLProductExtractor(
            timeout_s=120,
            max_cost="10",
            min_chars=50,
            max_chars=2000,
            debug=False,
            auto_retry_with_js=True
        )


def extract_result_to_dict(result: Any, extractor_type: str) -> Dict[str, Any]:
    """Convert extraction result to standardized dictionary format."""
    if extractor_type == "firecrawl":
        return {
            'url': result.url,
            'meta_title': result.meta_title,
            'meta_description': result.meta_description,
            'product_description': result.product_description,
            'product_name': result.product_name,
            'price': result.price,
            'features': result.features,
            'additional_information': result.additional_information,
            'extraction_method': result.extraction_method,
            'confidence_score': result.confidence_score,
        }
    else:
        return {
            'url': result.url,
            'meta_title': result.meta_title,
            'meta_description': result.meta_description,
            'product_description': result.product_description,
            'extraction_method': result.extraction_method,
            'confidence_score': result.confidence_score,
        }


@api_bp.route('/search', methods=['POST'])
def search_products() -> tuple[Dict[str, Any], int]:
    """
    Search for popular products using SERP API.

    Expected JSON:
    {
        "query": "wireless headphones"
    }

    Returns:
    {
        "status": "success",
        "products": [...]
    }
    """
    try:
        data = request.get_json()
        query = data.get('query', '').strip()

        if not query:
            return jsonify({
                'status': 'error',
                'message': 'Query is required'
            }), 400

        logger.info(f"Searching for products: {query}")

        # Fetch products using SERP API (fetch 10 to have buffer for extraction failures)
        aggregated = SerpProcessor.fetch_products(
            [query],
            limit=10,
            device='desktop',
            api_key=None  # Uses env SERP_API_KEY
        )

        # Enrich with organic links
        aggregated = SerpProcessor.enrich_with_first_organic_links(
            aggregated,
            device='desktop',
            api_key=None,
            engine='google',
            max_per_query=10
        )

        # Convert to response format
        products = []
        for query_key, hits_by_title in aggregated.by_query.items():
            for title, hit in hits_by_title.items():
                products.append({
                    'title': hit.title,
                    'price': hit.price,
                    'source': hit.source,
                    'link': hit.link
                })

        logger.info(f"Found {len(products)} products for query: {query}")

        # Check if we have products with valid links
        products_with_links = [p for p in products if p.get('link')]
        logger.info(f"Products with links: {len(products_with_links)} of {len(products)}")

        if not products:
            return jsonify({
                'status': 'error',
                'message': 'No products found for this query. Try a different search term.',
                'query': query
            }), 404

        if not products_with_links:
            logger.warning(f"Products found but none have valid links: {[p.get('title') for p in products[:3]]}")
            return jsonify({
                'status': 'error',
                'message': 'Products found but could not retrieve product URLs. This may be a SERP API issue.',
                'query': query,
                'products_found': len(products)
            }), 404

        return jsonify({
            'status': 'success',
            'query': query,
            'products': products_with_links,
            'count': len(products_with_links)
        })

    except Exception as e:
        logger.error(f"Error in search endpoint: {e}", exc_info=True)
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@api_bp.route('/extract', methods=['POST'])
def extract_description() -> tuple[Dict[str, Any], int]:
    """
    Extract product description from URL.

    Uses the configured extractor (html or firecrawl based on EXTRACTOR_TYPE).

    Expected JSON:
    {
        "url": "https://example.com/product"
    }

    Returns:
    {
        "status": "success",
        "data": {...}
    }
    """
    try:
        data = request.get_json()
        url = data.get('url', '').strip()

        if not url:
            return jsonify({
                'status': 'error',
                'message': 'URL is required'
            }), 400

        logger.info(f"Extracting from URL: {url} (extractor: {Config.EXTRACTOR_TYPE})")

        # Get configured extractor
        extractor = get_extractor()

        # Extract product information
        result = extractor.extract(url)

        logger.info(
            f"Extraction complete for {url}: "
            f"method={result.extraction_method}, "
            f"confidence={result.confidence_score:.2f}"
        )

        return jsonify({
            'status': 'success',
            'extractor_type': Config.EXTRACTOR_TYPE,
            'data': extract_result_to_dict(result, Config.EXTRACTOR_TYPE)
        })

    except Exception as e:
        logger.error(f"Error in extract endpoint: {e}", exc_info=True)
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@api_bp.route('/extract-batch', methods=['POST'])
def extract_batch() -> tuple[Dict[str, Any], int]:
    """
    Extract descriptions for multiple products with backup strategy.

    Uses the configured extractor (html or firecrawl based on EXTRACTOR_TYPE).

    Logic:
    - Try extracting the first 5 products in parallel
    - For each failure, use a backup product from positions 6-10
    - Target: 5 successful extractions

    Expected JSON:
    {
        "products": [
            {
                "title": "Product 1",
                "link": "https://...",
                "price": "$99",
                "source": "Amazon"
            },
            ...
        ],
        "target_count": 5  // Optional, default 5
    }

    Returns:
    {
        "status": "success",
        "results": [...],  // Successful extractions (target: 5)
        "failed": [...],   // Failed extractions
        "backups_used": [...] // Backup products that were used
    }
    """
    try:
        data = request.get_json()
        products = data.get('products', [])
        target_count = data.get('target_count', 5)

        if not products:
            return jsonify({
                'status': 'error',
                'message': 'Products list is required'
            }), 400

        # Filter products with valid URLs
        valid_products = [
            p for p in products
            if p.get('link', '').strip()
        ]

        if not valid_products:
            return jsonify({
                'status': 'error',
                'message': 'No products with valid URLs provided'
            }), 400

        # Split into primary (first 5) and backup products
        primary_products = valid_products[:target_count]
        backup_products = valid_products[target_count:]

        extractor_type = Config.EXTRACTOR_TYPE
        logger.info(f"Batch extraction: {len(primary_products)} primary, {len(backup_products)} backups "
                   f"(target: {target_count}, extractor: {extractor_type})")

        def extract_single(product: Dict[str, Any], index: int, is_backup: bool = False) -> Dict[str, Any]:
            """Extract product info for a single product."""
            url = product.get('link', '').strip()
            title = product.get('title', 'Unknown')
            price = product.get('price')
            source = product.get('source')

            try:
                # Get configured extractor (each thread gets its own instance)
                logger.info(f"Starting extraction for: {url}")
                extractor = get_extractor()
                result = extractor.extract(url)

                # Log extraction result details
                logger.info(f"Extraction result for {url}: "
                           f"method={result.extraction_method}, "
                           f"confidence={result.confidence_score}, "
                           f"has_description={bool(result.product_description)}")

                if result.product_description:
                    # Build result dict based on extractor type
                    result_dict = {
                        'index': index,
                        'title': title,
                        'price': price,
                        'source': source,
                        'url': result.url,
                        'meta_title': result.meta_title,
                        'meta_description': result.meta_description,
                        'product_description': result.product_description,
                        'extraction_method': result.extraction_method,
                        'confidence_score': result.confidence_score,
                        'is_backup': is_backup,
                        'success': True
                    }

                    # Add Firecrawl-specific fields if available
                    if extractor_type == "firecrawl":
                        result_dict['product_name'] = getattr(result, 'product_name', None)
                        result_dict['features'] = getattr(result, 'features', None)
                        result_dict['additional_information'] = getattr(result, 'additional_information', None)

                    return result_dict
                else:
                    logger.warning(f"No product description found for {url}. "
                                  f"Result details: method={result.extraction_method}, "
                                  f"product_name={getattr(result, 'product_name', None)}, "
                                  f"features={getattr(result, 'features', None)}")
                    return {
                        'index': index,
                        'title': title,
                        'price': price,
                        'source': source,
                        'url': url,
                        'error': 'No product description found',
                        'is_backup': is_backup,
                        'success': False
                    }
            except Exception as e:
                logger.error(f"Error extracting {url}: {e}")
                return {
                    'index': index,
                    'title': title,
                    'price': price,
                    'source': source,
                    'url': url,
                    'error': str(e),
                    'is_backup': is_backup,
                    'success': False
                }

        # Step 1: Extract primary products
        primary_results = []
        if Config.EXTRACTION_WORKERS <= 1:
            # Sequential extraction - saves memory on constrained environments
            for i, product in enumerate(primary_products):
                result = extract_single(product, i, False)
                primary_results.append(result)
                # Force garbage collection after each extraction
                import gc
                gc.collect()
        else:
            # Parallel extraction
            with ThreadPoolExecutor(max_workers=Config.EXTRACTION_WORKERS) as executor:
                futures = {
                    executor.submit(extract_single, product, i, False): i
                    for i, product in enumerate(primary_products)
                }
                for future in as_completed(futures):
                    primary_results.append(future.result())

        # Sort by original index to maintain order
        primary_results.sort(key=lambda x: x['index'])

        # Separate successful and failed
        successful = [r for r in primary_results if r.get('success')]
        failed = [r for r in primary_results if not r.get('success')]

        logger.info(f"Primary extraction: {len(successful)} successful, {len(failed)} failed")

        # Step 2: For each failure, try a backup product
        backups_used = []
        backup_index = 0

        while len(successful) < target_count and backup_index < len(backup_products):
            failures_to_replace = target_count - len(successful)
            backups_to_try = backup_products[backup_index:backup_index + failures_to_replace]

            if not backups_to_try:
                break

            logger.info(f"Trying {len(backups_to_try)} backup products...")

            # Extract backups
            backup_results = []
            if Config.EXTRACTION_WORKERS <= 1:
                # Sequential extraction
                for i, product in enumerate(backups_to_try):
                    result = extract_single(product, target_count + backup_index + i, True)
                    backup_results.append(result)
                    import gc
                    gc.collect()
            else:
                # Parallel extraction
                with ThreadPoolExecutor(max_workers=Config.EXTRACTION_WORKERS) as executor:
                    futures = {
                        executor.submit(extract_single, product, target_count + backup_index + i, True): i
                        for i, product in enumerate(backups_to_try)
                    }
                    for future in as_completed(futures):
                        backup_results.append(future.result())

            # Process backup results
            for result in backup_results:
                if result.get('success'):
                    successful.append(result)
                    backups_used.append({
                        'title': result['title'],
                        'url': result['url'],
                        'replaced_failed': True
                    })
                    logger.info(f"Backup succeeded: {result['title']}")
                else:
                    failed.append(result)
                    logger.warning(f"Backup also failed: {result['title']}")

            backup_index += len(backups_to_try)

        # Clean up internal flags from results
        for r in successful:
            r.pop('success', None)
            r.pop('index', None)
        for r in failed:
            r.pop('success', None)
            r.pop('index', None)

        logger.info(f"Final results: {len(successful)} successful, {len(failed)} failed, {len(backups_used)} backups used")

        return jsonify({
            'status': 'success',
            'extractor_type': extractor_type,
            'results': successful[:target_count],  # Ensure we don't exceed target
            'failed': failed,
            'backups_used': backups_used,
            'total_successful': len(successful),
            'total_failed': len(failed)
        })

    except Exception as e:
        logger.error(f"Error in extract-batch endpoint: {e}", exc_info=True)
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@api_bp.route('/seo/analyze', methods=['POST'])
def analyze_seo() -> tuple[Dict[str, Any], int]:
    """
    Perform SEO keyword analysis on extracted product data.

    Expected JSON:
    {
        "products": [
            {
                "product_name": "string",
                "features": [{"heading": "string", "description": "string"}],
                "additional_information": "string"
            },
            ...
        ],
        "config": {  // Optional
            "top_n": 500,
            "min_df": 2,
            "brands": ["brand1", "brand2"]
        }
    }

    Returns:
    {
        "status": "success",
        "analysis": {
            "phrases": [...],
            "statistics": {...}
        }
    }
    """
    try:
        data = request.get_json()
        products = data.get('products', [])
        config = data.get('config', {})

        if not products:
            return jsonify({
                'status': 'error',
                'message': 'Products list is required'
            }), 400

        logger.info(f"Starting SEO analysis on {len(products)} products")

        # Initialize analyzer with config
        analyzer = SEOAnalyzer(
            top_n_phrases=config.get('top_n', 500),
            min_doc_freq=config.get('min_df', 2),
            brand_names=set(config.get('brands', []))
        )

        # Perform analysis
        result = analyzer.analyze(products)

        logger.info(f"SEO analysis complete: {result.unique_phrases} phrases extracted")

        return jsonify({
            'status': 'success',
            'analysis': result.to_dict()
        })

    except Exception as e:
        logger.error(f"Error in SEO analyze endpoint: {e}", exc_info=True)
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@api_bp.route('/seo/analyze-extraction', methods=['POST'])
def analyze_seo_from_extraction() -> tuple[Dict[str, Any], int]:
    """
    Perform SEO analysis on batch extraction results.

    This endpoint accepts the format returned by /api/extract-batch.

    Expected JSON:
    {
        "results": [...],  // Results from extract-batch
        "config": {  // Optional
            "top_n": 500,
            "min_df": 2
        }
    }

    Returns:
    {
        "status": "success",
        "analysis": {...}
    }
    """
    try:
        data = request.get_json()
        results = data.get('results', [])
        config = data.get('config', {})

        if not results:
            return jsonify({
                'status': 'error',
                'message': 'Extraction results are required'
            }), 400

        logger.info(f"Starting SEO analysis on {len(results)} extraction results")

        # Initialize analyzer
        analyzer = SEOAnalyzer(
            top_n_phrases=config.get('top_n', 500),
            min_doc_freq=config.get('min_df', 2),
            brand_names=set(config.get('brands', []))
        )

        # Perform analysis from extraction results
        result = analyzer.analyze_from_extraction_results(results)

        logger.info(f"SEO analysis complete: {result.unique_phrases} phrases extracted")

        return jsonify({
            'status': 'success',
            'analysis': result.to_dict()
        })

    except Exception as e:
        logger.error(f"Error in SEO analyze-extraction endpoint: {e}", exc_info=True)
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@api_bp.route('/seo/export-csv', methods=['POST'])
def export_seo_csv() -> Any:
    """
    Export SEO analysis results as CSV.

    Expected JSON:
    {
        "phrases": [...]  // Phrases from analysis result
    }

    Returns: CSV file download
    """
    try:
        data = request.get_json()
        phrases = data.get('phrases', [])

        if not phrases:
            return jsonify({
                'status': 'error',
                'message': 'Phrases data is required'
            }), 400

        # Build CSV content
        import csv
        import io

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
        for phrase in phrases:
            writer.writerow([
                phrase.get('phrase', ''),
                phrase.get('doc_freq', 0),
                phrase.get('total_occurrences', 0),
                round(phrase.get('tfidf_score', 0), 4),
                round(phrase.get('importance_score', 0), 2),
                phrase.get('source', '')
            ])

        csv_content = output.getvalue()

        return Response(
            csv_content,
            mimetype='text/csv',
            headers={
                'Content-Disposition': 'attachment; filename=seo_phrases.csv',
                'Content-Type': 'text/csv; charset=utf-8'
            }
        )

    except Exception as e:
        logger.error(f"Error in SEO export-csv endpoint: {e}", exc_info=True)
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@api_bp.route('/seo/generate-description', methods=['POST'])
def generate_description() -> tuple[Dict[str, Any], int]:
    """
    Generate a single SEO-optimized description from all products and keywords.

    Combines extracted data from multiple products and identified keywords
    to generate ONE unified product description.

    Expected JSON:
    {
        "products": [
            {
                "product_name": "Product Name",
                "price": "$99.99",
                "features": [...],
                "additional_information": {...},
                "product_description": "..."
            },
            ...
        ],
        "keywords": [
            {"phrase": "keyword", "importance_score": 0.95},
            ...
        ],
        "product_name": "Optional override name",  // Optional
        "config": {  // Optional
            "model": "gpt-4o-mini",
            "temperature": 0.7
        }
    }

    Returns:
    {
        "status": "success",
        "result": {
            "product_name": "...",
            "description": "...",
            "word_count": 85,
            "keywords_used": [...],
            "products_combined": 5
        }
    }
    """
    try:
        data = request.get_json()
        products = data.get('products', [])
        keywords = data.get('keywords', [])
        product_name_override = data.get('product_name')
        search_query = data.get('search_query', '')  # Use search query as generic product name
        config = data.get('config', {})

        # Prefer search_query over product_name for generic naming
        if search_query and not product_name_override:
            product_name_override = search_query

        if not products:
            return jsonify({
                'status': 'error',
                'message': 'Products list is required'
            }), 400

        if not keywords:
            return jsonify({
                'status': 'error',
                'message': 'Keywords are required for description generation'
            }), 400

        logger.info(f"Generating single description from {len(products)} products and {len(keywords)} keywords")

        # Initialize generator
        generator = DescriptionGenerator(
            model=config.get('model', 'gpt-4o-mini'),
            temperature=config.get('temperature', 0.7)
        )

        # Generate single description from all products and keywords
        result = generator.generate(
            products=products,
            keywords=keywords,
            product_name=product_name_override
        )

        if not result.success:
            return jsonify({
                'status': 'error',
                'message': result.error or 'Description generation failed'
            }), 500

        logger.info(f"Generated description: {result.word_count} words from {result.products_combined} products")

        return jsonify({
            'status': 'success',
            'result': {
                'product_name': result.product_name,
                'price': result.price,
                'description': result.description,
                'word_count': result.word_count,
                'keywords_used': result.keywords_used,
                'model_used': result.model_used,
                'products_combined': result.products_combined,
                'source_text_preview': result.source_text[:500] + '...' if len(result.source_text) > 500 else result.source_text
            }
        })

    except Exception as e:
        logger.error(f"Error in generate-description endpoint: {e}", exc_info=True)
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@api_bp.route('/seo/export-description', methods=['POST'])
def export_description() -> Any:
    """
    Export generated description as a text file or JSON.

    Expected JSON:
    {
        "description": {
            "product_name": "Product Name",
            "description": "SEO optimized description...",
            "price": "$99.99",
            "keywords_used": [...],
            "products_combined": 5
        },
        "format": "txt" or "json"  // Default: txt
    }

    Returns: Text or JSON file download
    """
    try:
        data = request.get_json()
        description_data = data.get('description', {})
        export_format = data.get('format', 'txt').lower()

        if not description_data or not description_data.get('description'):
            return jsonify({
                'status': 'error',
                'message': 'Description data is required'
            }), 400

        if export_format == 'json':
            # Export as JSON
            import json
            json_content = json.dumps(description_data, indent=2)

            return Response(
                json_content,
                mimetype='application/json',
                headers={
                    'Content-Disposition': 'attachment; filename=seo_description.json',
                    'Content-Type': 'application/json; charset=utf-8'
                }
            )
        else:
            # Export as formatted text
            product_name = description_data.get('product_name', 'Product')
            price = description_data.get('price', '')
            description = description_data.get('description', '')
            keywords = description_data.get('keywords_used', [])
            products_combined = description_data.get('products_combined', 1)
            word_count = description_data.get('word_count', len(description.split()))

            lines = [
                "=" * 60,
                "SEO-OPTIMIZED PRODUCT DESCRIPTION",
                "=" * 60,
                "",
                f"Product: {product_name}",
            ]

            if price:
                lines.append(f"Price: {price}")

            lines.extend([
                f"Products Combined: {products_combined}",
                f"Word Count: {word_count}",
                "",
                "-" * 60,
                "DESCRIPTION",
                "-" * 60,
                "",
                description,
                "",
            ])

            if keywords:
                lines.extend([
                    "-" * 60,
                    "KEYWORDS USED",
                    "-" * 60,
                    "",
                    ", ".join(keywords),
                    "",
                ])

            lines.extend([
                "=" * 60,
                "Generated by Inlined SEO Description Generator",
                "=" * 60,
            ])

            txt_content = "\n".join(lines)

            return Response(
                txt_content,
                mimetype='text/plain',
                headers={
                    'Content-Disposition': 'attachment; filename=seo_description.txt',
                    'Content-Type': 'text/plain; charset=utf-8'
                }
            )

    except Exception as e:
        logger.error(f"Error in export-description endpoint: {e}", exc_info=True)
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


# ============================================================================
# ENTITY EXTRACTION ENDPOINTS
# ============================================================================

# Simple in-memory cache for entity results
from datetime import datetime, timedelta, timezone
_entity_cache: Dict[str, tuple] = {}  # {cache_key: (result_dict, timestamp)}
ENTITY_CACHE_TTL = timedelta(minutes=5)


def _get_entity_cache_key(product_id: str, terms_hash: int) -> str:
    """Generate cache key for entity results."""
    return f"entity:{product_id}:{terms_hash}"


def _check_entity_cache(cache_key: str) -> Optional[Dict]:
    """Check if valid cached result exists."""
    if cache_key in _entity_cache:
        result, timestamp = _entity_cache[cache_key]
        if datetime.now(timezone.utc) - timestamp < ENTITY_CACHE_TTL:
            return result
        else:
            # Expired, remove from cache
            del _entity_cache[cache_key]
    return None


def _set_entity_cache(cache_key: str, result: Dict) -> None:
    """Store result in cache."""
    _entity_cache[cache_key] = (result, datetime.now(timezone.utc))
    # Simple cache cleanup: remove entries if cache gets too large
    if len(_entity_cache) > 100:
        # Remove oldest 20 entries
        sorted_keys = sorted(_entity_cache.keys(), key=lambda k: _entity_cache[k][1])
        for key in sorted_keys[:20]:
            del _entity_cache[key]


@api_bp.route('/entities/extract', methods=['POST'])
def extract_entities() -> tuple[Dict[str, Any], int]:
    """
    Extract entities using hybrid rules + LLM approach.

    Performs:
    1. Groups TF-IDF terms into 4 buckets (Core Attributes, Functional, Context, Compliance)
    2. Runs deterministic rules extraction (fast, consistent)
    3. If confidence < 0.7 or critical types missing, invokes LLM
    4. Merges results with rules preference
    5. Creates placement recommendations for PDP sections

    Expected JSON:
    {
        "product_id": "unique-id",
        "product_name": "Product Name",
        "tfidf_terms": [
            {"phrase": "term", "tfidf_score": 0.95, "doc_freq": 3},
            ...
        ],
        "product_description": "Full product description (optional)",
        "force_llm": false  // Optional: force LLM extraction
    }

    Returns:
    {
        "status": "success",
        "cached": false,
        "entity_result": {
            "product_id": "...",
            "product_name": "...",
            "primary_entity_path": "Appliance > Cooktop > Induction",
            "grouped_terms": {...},
            "rule_entities": [...],   // Entities from rules
            "llm_entities": [...],    // Entities from LLM (if invoked)
            "supporting_entities": [...],  // Final merged entities
            "placement_map": [...],
            "noise_terms": [...],
            "confidence": 0.85,
            "audit": {
                "missing_types": [...],
                "conflicts": [...],
                "notes": [...],
                "llm_invoked": false,
                "llm_reason": null
            }
        }
    }
    """
    try:
        data = request.get_json()
        product_id = data.get('product_id', '')
        product_name = data.get('product_name', '')
        search_query = data.get('search_query', '')  # Original search term for context
        tfidf_terms = data.get('tfidf_terms', [])
        product_description = data.get('product_description')
        force_llm = data.get('force_llm', False)

        if not product_id or not product_name:
            return jsonify({
                'status': 'error',
                'message': 'product_id and product_name are required'
            }), 400

        if not tfidf_terms:
            return jsonify({
                'status': 'error',
                'message': 'tfidf_terms are required'
            }), 400

        # Check cache (skip if force_llm as that might produce different results)
        if not force_llm:
            terms_hash = hash(str(tfidf_terms[:10]))  # Hash first 10 terms
            cache_key = _get_entity_cache_key(product_id, terms_hash)
            cached_result = _check_entity_cache(cache_key)
            if cached_result:
                logger.info(f"Returning cached entity result for: {product_name}")
                return jsonify({
                    'status': 'success',
                    'cached': True,
                    'entity_result': cached_result
                })

        logger.info(f"Extracting entities for product: {product_name} ({len(tfidf_terms)} TF-IDF terms, force_llm={force_llm})")

        # Initialize entity extractor
        entity_extractor = EntityExtractor()

        # Extract entities using hybrid approach
        # Pass search_query for better LLM context (helps understand product type)
        entity_result = entity_extractor.extract_entities(
            product_id=product_id,
            product_name=product_name,
            tfidf_terms=tfidf_terms,
            product_description=product_description,
            force_llm=force_llm,
            search_query=search_query
        )

        result_dict = entity_result.to_dict()

        # Cache the result (unless force_llm was used)
        if not force_llm:
            _set_entity_cache(cache_key, result_dict)

        logger.info(f"Entity extraction complete: primary={entity_result.primary_entity_path}, "
                   f"entities={len(entity_result.supporting_entities)}, "
                   f"confidence={entity_result.confidence:.2f}, "
                   f"llm_invoked={entity_result.audit.llm_invoked}")

        return jsonify({
            'status': 'success',
            'cached': False,
            'entity_result': result_dict
        })

    except Exception as e:
        logger.error(f"Error in entity extraction endpoint: {e}", exc_info=True)
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@api_bp.route('/entities/extract-batch', methods=['POST'])
def extract_entities_batch() -> tuple[Dict[str, Any], int]:
    """
    Extract entities from multiple products at once.

    Expected JSON:
    {
        "products": [
            {
                "product_id": "id1",
                "product_name": "Product Name",
                "tfidf_terms": [...],
                "product_description": "..."
            },
            ...
        ]
    }

    Returns:
    {
        "status": "success",
        "results": [
            {
                "product_id": "...",
                "entity_result": {...}
            },
            ...
        ],
        "total": 5
    }
    """
    try:
        data = request.get_json()
        products = data.get('products', [])

        if not products:
            return jsonify({
                'status': 'error',
                'message': 'Products list is required'
            }), 400

        logger.info(f"Extracting entities for {len(products)} products")

        # Initialize entity extractor
        entity_extractor = EntityExtractor()

        results = []
        for product in products:
            try:
                product_id = product.get('product_id', '')
                product_name = product.get('product_name', '')
                tfidf_terms = product.get('tfidf_terms', [])
                product_description = product.get('product_description')

                if not product_id or not product_name or not tfidf_terms:
                    logger.warning(f"Skipping product with missing fields: {product_id}")
                    continue

                entity_result = entity_extractor.extract_entities(
                    product_id=product_id,
                    product_name=product_name,
                    tfidf_terms=tfidf_terms,
                    product_description=product_description
                )

                results.append({
                    'product_id': product_id,
                    'entity_result': entity_result.to_dict()
                })

            except Exception as e:
                logger.error(f"Error extracting entities for product {product.get('product_id')}: {e}")
                results.append({
                    'product_id': product.get('product_id'),
                    'error': str(e)
                })

        logger.info(f"Batch entity extraction complete: {len(results)} products processed")

        return jsonify({
            'status': 'success',
            'results': results,
            'total': len(results)
        })

    except Exception as e:
        logger.error(f"Error in batch entity extraction endpoint: {e}", exc_info=True)
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500
