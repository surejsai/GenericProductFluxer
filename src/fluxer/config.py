"""
Configuration management for Fluxer.
"""
import os
from typing import Optional
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv not available


class Config:
    """Application configuration."""

    # Project paths
    PROJECT_ROOT = Path(__file__).parent.parent.parent
    SRC_DIR = PROJECT_ROOT / "src"
    TEMPLATES_DIR = PROJECT_ROOT / "templates"
    STATIC_DIR = PROJECT_ROOT / "static"

    # API Keys
    SERP_API_KEY: Optional[str] = os.getenv("SERP_API_KEY")
    SCRAPER_API_KEY: Optional[str] = os.getenv("SCRAPER_API_KEY")
    FIRECRAWL_API_KEY: Optional[str] = os.getenv("FIRECRAWL_API_KEY")

    # Extractor configuration
    # Options: "html" (ScraperAPI + custom parsing) or "firecrawl" (Firecrawl LLM extraction)
    EXTRACTOR_TYPE: str = os.getenv("EXTRACTOR_TYPE", "firecrawl")

    # Flask settings
    FLASK_ENV: str = os.getenv("FLASK_ENV", "development")
    FLASK_DEBUG: bool = os.getenv("FLASK_DEBUG", "True").lower() == "true"
    FLASK_HOST: str = os.getenv("FLASK_HOST", "0.0.0.0")
    FLASK_PORT: int = int(os.getenv("FLASK_PORT", "5000"))

    # Extraction defaults
    DEFAULT_TIMEOUT_S: int = 120
    DEFAULT_MAX_COST: str = "10"
    DEFAULT_MIN_CHARS: int = 50
    DEFAULT_MAX_CHARS: int = 2000

    # SERP defaults
    DEFAULT_SERP_LIMIT: int = 5
    DEFAULT_SERP_DEVICE: str = "desktop"

    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    @classmethod
    def validate(cls) -> list[str]:
        """
        Validate configuration.

        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []

        if not cls.SERP_API_KEY:
            errors.append("SERP_API_KEY not set in environment")

        # Validate extractor-specific API keys
        if cls.EXTRACTOR_TYPE == "html" and not cls.SCRAPER_API_KEY:
            errors.append("SCRAPER_API_KEY not set (required for html extractor)")
        elif cls.EXTRACTOR_TYPE == "firecrawl" and not cls.FIRECRAWL_API_KEY:
            errors.append("FIRECRAWL_API_KEY not set (required for firecrawl extractor)")

        if cls.EXTRACTOR_TYPE not in ("html", "firecrawl"):
            errors.append(f"Invalid EXTRACTOR_TYPE: {cls.EXTRACTOR_TYPE}. Must be 'html' or 'firecrawl'")

        if not cls.TEMPLATES_DIR.exists():
            errors.append(f"Templates directory not found: {cls.TEMPLATES_DIR}")

        return errors

    @classmethod
    def is_valid(cls) -> bool:
        """Check if configuration is valid."""
        return len(cls.validate()) == 0

    @classmethod
    def get_summary(cls) -> dict:
        """Get configuration summary (safe for logging)."""
        return {
            "flask_env": cls.FLASK_ENV,
            "flask_debug": cls.FLASK_DEBUG,
            "extractor_type": cls.EXTRACTOR_TYPE,
            "serp_api_configured": cls.SERP_API_KEY is not None,
            "scraper_api_configured": cls.SCRAPER_API_KEY is not None,
            "firecrawl_api_configured": cls.FIRECRAWL_API_KEY is not None,
            "log_level": cls.LOG_LEVEL,
        }
