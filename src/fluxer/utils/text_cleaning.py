"""
Text cleaning and normalization utilities.
"""
import re
from html import unescape
from typing import Optional


def normalize_whitespace(text: str) -> str:
    """
    Normalize whitespace in text.

    Args:
        text: Text to normalize

    Returns:
        Text with normalized whitespace

    Examples:
        >>> normalize_whitespace("hello    world\\n\\ntest")
        'hello world test'
    """
    if not text:
        return ""

    # Replace multiple whitespace with single space
    text = re.sub(r'\s+', ' ', text)

    # Strip leading/trailing whitespace
    return text.strip()


def strip_html_tags(text: str) -> str:
    """
    Remove HTML tags from text.

    Args:
        text: Text with HTML tags

    Returns:
        Text without HTML tags

    Examples:
        >>> strip_html_tags("<p>Hello <strong>world</strong></p>")
        'Hello world'
    """
    if not text:
        return ""

    # Remove HTML tags
    text = re.sub(r'<[^>]+>', '', text)

    # Unescape HTML entities
    text = unescape(text)

    return text


def clean_text(
    text: str,
    strip_html: bool = True,
    normalize_ws: bool = True,
    remove_urls: bool = False,
) -> str:
    """
    Clean and normalize text.

    Args:
        text: Text to clean
        strip_html: Remove HTML tags
        normalize_ws: Normalize whitespace
        remove_urls: Remove URLs from text

    Returns:
        Cleaned text

    Examples:
        >>> clean_text("<p>Hello  world</p>")
        'Hello world'
    """
    if not text:
        return ""

    # Strip HTML if requested
    if strip_html:
        text = strip_html_tags(text)

    # Remove URLs if requested
    if remove_urls:
        text = re.sub(r'https?://\S+', '', text)

    # Normalize whitespace if requested
    if normalize_ws:
        text = normalize_whitespace(text)

    return text


def truncate_text(text: str, max_length: int, suffix: str = "...") -> str:
    """
    Truncate text to maximum length.

    Args:
        text: Text to truncate
        max_length: Maximum length
        suffix: Suffix to add if truncated

    Returns:
        Truncated text

    Examples:
        >>> truncate_text("Hello world", 8)
        'Hello...'
    """
    if not text or len(text) <= max_length:
        return text

    # Account for suffix length
    truncate_at = max_length - len(suffix)

    return text[:truncate_at] + suffix


def extract_numbers(text: str) -> list[float]:
    """
    Extract numbers from text.

    Args:
        text: Text containing numbers

    Returns:
        List of extracted numbers

    Examples:
        >>> extract_numbers("Price: $19.99 was $29.99")
        [19.99, 29.99]
    """
    if not text:
        return []

    # Pattern for numbers (including decimals)
    pattern = r'-?\d+(?:\.\d+)?'

    matches = re.findall(pattern, text)

    return [float(match) for match in matches]


def remove_special_chars(text: str, keep_spaces: bool = True) -> str:
    """
    Remove special characters from text.

    Args:
        text: Text to clean
        keep_spaces: Keep spaces in text

    Returns:
        Text without special characters

    Examples:
        >>> remove_special_chars("Hello! World?")
        'Hello World'
    """
    if not text:
        return ""

    if keep_spaces:
        # Keep letters, numbers, and spaces
        return re.sub(r'[^a-zA-Z0-9\s]', '', text)
    else:
        # Keep only letters and numbers
        return re.sub(r'[^a-zA-Z0-9]', '', text)
