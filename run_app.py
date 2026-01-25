"""
Main entry point for Fluxer Atelier web application.

Run this file to start the Flask development server.
"""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from fluxer.api import create_app
from fluxer.config import Config
from fluxer.logger import get_logger

logger = get_logger(__name__)


def main():
    """Main function to run the Flask app."""
    # Validate configuration
    errors = Config.validate()
    if errors:
        logger.error("Configuration errors:")
        for error in errors:
            logger.error(f"  - {error}")
        logger.warning("App will start but some features may not work")

    # Create app
    app = create_app()

    # Run app
    logger.info(f"Starting Flask app on {Config.FLASK_HOST}:{Config.FLASK_PORT}")
    logger.info(f"Debug mode: {Config.FLASK_DEBUG}")

    app.run(
        host=Config.FLASK_HOST,
        port=Config.FLASK_PORT,
        debug=Config.FLASK_DEBUG
    )


if __name__ == "__main__":
    main()
