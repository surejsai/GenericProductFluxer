"""
Input validation utilities.
"""
import re
from typing import Optional
from urllib.parse import urlparse


def is_valid_url(url: str) -> bool:
    """
    Check if a string is a valid HTTP/HTTPS URL.

    Args:
        url: URL string to validate

    Returns:
        True if URL is valid, False otherwise
    """
    if not url or not isinstance(url, str):
        return False

    try:
        result = urlparse(url)
        return all([
            result.scheme in ("http", "https"),
            result.netloc,
        ])
    except Exception:
        return False


def validate_url(url: str) -> Optional[str]:
    """
    Validate and normalize a URL.

    Args:
        url: URL string to validate

    Returns:
        Normalized URL if valid, None otherwise

    Examples:
        >>> validate_url("https://example.com")
        'https://example.com'
        >>> validate_url("not a url")
        None
    """
    if not is_valid_url(url):
        return None

    # Ensure it starts with http:// or https://
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    # Remove trailing slashes
    url = url.rstrip("/")

    return url if is_valid_url(url) else None


def is_valid_price(price: str) -> bool:
    """
    Check if a string looks like a valid price.

    Args:
        price: Price string to validate

    Returns:
        True if price looks valid, False otherwise

    Examples:
        >>> is_valid_price("$19.99")
        True
        >>> is_valid_price("invalid")
        False
    """
    if not price or not isinstance(price, str):
        return False

    # Pattern for common price formats
    price_pattern = r"[$£€¥]\s*\d+(?:[.,]\d{2})?"
    return bool(re.search(price_pattern, price))


def sanitize_filename(filename: str, max_length: int = 255) -> str:
    """
    Sanitize a string for use as a filename.

    Args:
        filename: Original filename
        max_length: Maximum length for filename

    Returns:
        Sanitized filename

    Examples:
        >>> sanitize_filename("product: name/test")
        'product_name_test'
    """
    # Remove invalid characters
    sanitized = re.sub(r'[<>:"/\\|?*]', "_", filename)

    # Remove leading/trailing whitespace and dots
    sanitized = sanitized.strip(" .")

    # Truncate if too long
    if len(sanitized) > max_length:
        sanitized = sanitized[:max_length]

    return sanitized or "untitled"
