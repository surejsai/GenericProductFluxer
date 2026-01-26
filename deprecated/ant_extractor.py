#!/usr/bin/env python3
"""
Universal Product Description Extractor
Extract product information from any product page URL using AI
"""

import os
import requests
from bs4 import BeautifulSoup
import json
import sys

def fetch_page_content(url):
    """Fetch HTML content from a URL"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        return response.text
    except requests.exceptions.RequestException as e:
        print(f"Error fetching URL: {e}")
        return None

def clean_html(html_content):
    """Extract text content from HTML, removing scripts and styles"""
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Remove script and style elements
    for script in soup(['script', 'style', 'nav', 'header', 'footer']):
        script.decompose()
    
    return str(soup)

def extract_with_anthropic(html_content, url):
    """Use Anthropic API to extract product information"""
    
    # API key from environment variable
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("Error: ANTHROPIC_API_KEY environment variable not set")
        return None
    
    # Truncate HTML if too long (keep first 40000 chars to stay within limits)
    truncated_html = html_content[:40000]
    
    prompt = f"""I have the HTML content from a product page at {url}. Please analyze it and extract all product information.

HTML Content:
{truncated_html}

Your task is to extract:
1. Product name/title
2. Main product description
3. Product specifications (dimensions, materials, technical details, etc.)
4. Features and benefits
5. Price (if available)
6. Any other relevant product details

Please identify and extract ALL relevant product information. Look for content in various HTML elements. Ignore navigation menus, footers, and other non-product content.

Return ONLY a JSON object with no preamble or markdown formatting:
{{
  "productName": "extracted product name",
  "price": "price if available",
  "description": "main product description with all paragraphs",
  "specifications": "technical specs formatted clearly",
  "features": "key features as a list or paragraphs",
  "additionalInfo": "any other relevant product details"
}}"""

    headers = {
        'Content-Type': 'application/json',
        'x-api-key': api_key,
        'anthropic-version': '2023-06-01'
    }
    
    data = {
        'model': 'claude-sonnet-4-20250514',
        'max_tokens': 4000,
        'messages': [
            {
                'role': 'user',
                'content': prompt
            }
        ]
    }
    
    try:
        response = requests.post(
            'https://api.anthropic.com/v1/messages',
            headers=headers,
            json=data,
            timeout=60
        )
        response.raise_for_status()
        
        result = response.json()
        
        # Extract text from response
        text_content = ''
        for block in result.get('content', []):
            if block.get('type') == 'text':
                text_content += block.get('text', '')
        
        # Parse JSON from response
        # Remove markdown code blocks if present
        cleaned = text_content.replace('```json', '').replace('```', '').strip()
        product_data = json.loads(cleaned)
        
        return product_data
        
    except requests.exceptions.RequestException as e:
        print(f"Error calling Anthropic API: {e}")
        return None
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON response: {e}")
        print(f"Response text: {text_content}")
        return None

def extract_product_info(url):
    """Main function to extract product information from a URL"""
    print(f"Fetching content from: {url}")
    
    # Fetch the page
    html_content = fetch_page_content(url)
    if not html_content:
        return None
    
    print("Processing content with AI...")
    
    # Clean HTML
    cleaned_html = clean_html(html_content)
    
    # Extract with AI
    product_data = extract_with_anthropic(cleaned_html, url)
    
    return product_data

def main():
    """Main entry point"""
    if len(sys.argv) < 2:
        print("Usage: python product_extractor.py <URL>")
        print("\nExample:")
        print("  python product_extractor.py https://www.example.com/product/123")
        sys.exit(1)
    
    url = sys.argv[1]
    
    # Extract product information
    product_data = extract_product_info(url)
    
    if product_data:
        print("\n" + "="*60)
        print("EXTRACTED PRODUCT INFORMATION")
        print("="*60)
        print(json.dumps(product_data, indent=2, ensure_ascii=False))
        
        # Optionally save to file
        output_file = "product_data.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(product_data, f, indent=2, ensure_ascii=False)
        print(f"\n✓ Saved to {output_file}")
    else:
        print("Failed to extract product information")
        sys.exit(1)

if __name__ == "__main__":
    main()