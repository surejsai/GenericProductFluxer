"""
WSGI entry point for production deployment.

Use this file with a WSGI server like gunicorn or waitress:

    # Linux/Mac with gunicorn
    gunicorn wsgi:app --bind 0.0.0.0:5000 --workers 4

    # Windows with waitress
    waitress-serve --host=0.0.0.0 --port=5000 wsgi:app

    # Or use the CLI
    python wsgi.py
"""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from fluxer.api import create_app
from fluxer.config import Config
from fluxer.logger import get_logger

logger = get_logger(__name__)

# Create the Flask application instance
app = create_app()


def main():
    """Run with a production-ready server."""
    import os

    host = Config.FLASK_HOST
    port = Config.FLASK_PORT
    debug = Config.FLASK_DEBUG

    # Log configuration
    errors = Config.validate()
    if errors:
        logger.warning("Configuration warnings:")
        for error in errors:
            logger.warning(f"  - {error}")

    logger.info(f"Starting Fluxer on {host}:{port}")
    logger.info(f"Environment: {Config.FLASK_ENV}")
    logger.info(f"Debug: {debug}")

    # Use waitress for production (cross-platform)
    if Config.FLASK_ENV == "production" or not debug:
        try:
            from waitress import serve
            logger.info("Using Waitress production server")
            serve(app, host=host, port=port, threads=4)
        except ImportError:
            logger.warning("Waitress not installed, falling back to Flask dev server")
            logger.warning("Install waitress for production: pip install waitress")
            app.run(host=host, port=port, debug=debug)
    else:
        # Development mode - use Flask's built-in server
        logger.info("Using Flask development server")
        app.run(host=host, port=port, debug=debug)


if __name__ == "__main__":
    main()
