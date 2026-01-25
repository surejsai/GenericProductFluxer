"""
Flask backend for Fluxer Atelier - Product extraction web application.
"""
from __future__ import annotations

from flask import Flask, render_template, request, jsonify, send_from_directory
from flask_cors import CORS
import os
import sys
from typing import Optional

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from serp_services.get_popular_products import SerpProcessor
from html_product_extractor import HTMLProductExtractor

app = Flask(__name__, static_folder='static', template_folder='templates')
CORS(app)  # Enable CORS for development

# Initialize extractors (will use env variables for API keys)
html_extractor = HTMLProductExtractor(
    timeout_s=120,
    max_cost="10",
    min_chars=50,
    max_chars=2000,
    debug=False,
    auto_retry_with_js=True
)


@app.route('/')
def index():
    """Serve the main application page."""
    return render_template('index.html')


@app.route('/api/search', methods=['POST'])
def search_products():
    """
    Step 1: Search for popular products using SERP API.

    Expected JSON:
    {
        "query": "wireless headphones"
    }

    Returns:
    {
        "status": "success",
        "products": [
            {
                "title": "Product Name",
                "price": "$99.99",
                "source": "Amazon",
                "link": "https://..."
            },
            ...
        ]
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

        # Fetch products using SERP API
        aggregated = SerpProcessor.fetch_products(
            [query],
            limit=5,
            device='desktop',
            api_key=None  # Uses env SERP_API_KEY
        )

        # Enrich with organic links
        aggregated = SerpProcessor.enrich_with_first_organic_links(
            aggregated,
            device='desktop',
            api_key=None,
            engine='google',
            max_per_query=5
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

        return jsonify({
            'status': 'success',
            'query': query,
            'products': products,
            'count': len(products)
        })

    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@app.route('/api/extract', methods=['POST'])
def extract_description():
    """
    Step 2: Extract product description from URL.

    Expected JSON:
    {
        "url": "https://example.com/product"
    }

    Returns:
    {
        "status": "success",
        "data": {
            "url": "https://...",
            "meta_title": "Product Title",
            "meta_description": "Short description",
            "product_description": "Full description",
            "extraction_method": "jsonld",
            "confidence_score": 0.95
        }
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

        # Extract product information
        result = html_extractor.extract(url)

        return jsonify({
            'status': 'success',
            'data': {
                'url': result.url,
                'meta_title': result.meta_title,
                'meta_description': result.meta_description,
                'product_description': result.product_description,
                'extraction_method': result.extraction_method,
                'confidence_score': result.confidence_score
            }
        })

    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@app.route('/api/extract-batch', methods=['POST'])
def extract_batch():
    """
    Extract descriptions for multiple products.

    Expected JSON:
    {
        "products": [
            {
                "title": "Product 1",
                "link": "https://..."
            },
            ...
        ]
    }

    Returns:
    {
        "status": "success",
        "results": [
            {
                "title": "Product 1",
                "url": "https://...",
                "meta_title": "...",
                "meta_description": "...",
                "product_description": "...",
                "extraction_method": "...",
                "confidence_score": 0.95
            },
            ...
        ]
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

        results = []
        for product in products:
            url = product.get('link', '').strip()
            title = product.get('title', 'Unknown')

            if not url:
                results.append({
                    'title': title,
                    'url': None,
                    'error': 'No URL provided'
                })
                continue

            try:
                # Extract product information
                result = html_extractor.extract(url)

                results.append({
                    'title': title,
                    'url': result.url,
                    'meta_title': result.meta_title,
                    'meta_description': result.meta_description,
                    'product_description': result.product_description,
                    'extraction_method': result.extraction_method,
                    'confidence_score': result.confidence_score
                })
            except Exception as e:
                results.append({
                    'title': title,
                    'url': url,
                    'error': str(e)
                })

        return jsonify({
            'status': 'success',
            'results': results,
            'total': len(results),
            'successful': sum(1 for r in results if 'error' not in r)
        })

    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


if __name__ == '__main__':
    # Check if API keys are configured
    if not os.getenv('SERP_API_KEY'):
        print("WARNING: SERP_API_KEY not set. SERP API calls will fail.")
    if not os.getenv('SCRAPER_API_KEY'):
        print("WARNING: SCRAPER_API_KEY not set. Product extraction will fail.")

    # Run the Flask app
    app.run(debug=True, host='0.0.0.0', port=5000)
