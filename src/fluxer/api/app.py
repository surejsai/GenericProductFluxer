"""
Flask application factory for Fluxer.
"""
from flask import Flask, render_template
from flask_cors import CORS

from ..config import Config
from ..logger import get_logger
from .routes import api_bp

logger = get_logger(__name__)


def create_app() -> Flask:
    """
    Create and configure Flask application.

    Returns:
        Configured Flask app instance
    """
    # Create Flask app
    app = Flask(
        __name__,
        template_folder=str(Config.TEMPLATES_DIR),
        static_folder=str(Config.STATIC_DIR) if Config.STATIC_DIR.exists() else None
    )

    # Configure app
    app.config['SECRET_KEY'] = Config.SECRET_KEY
    app.config['ENV'] = Config.FLASK_ENV

    # Enable CORS with configured origins
    cors_origins = Config.get_cors_origins()
    if cors_origins == ["*"]:
        CORS(app)
    else:
        CORS(app, origins=cors_origins)

    # Register blueprints
    app.register_blueprint(api_bp)

    # Main route
    @app.route('/')
    def index():
        """Serve the main application page."""
        return render_template('index.html')

    # SEO Analysis page
    @app.route('/seo')
    def seo_page():
        """Serve the SEO analysis page."""
        return render_template('seo.html')

    # Description Generator page
    @app.route('/generate')
    def generate_page():
        """Serve the SEO description generator page."""
        return render_template('generate.html')

    # Entity Analysis page
    @app.route('/entities')
    def entities_page():
        """Serve the entity analysis page."""
        return render_template('entities.html')

    # Health check
    @app.route('/health')
    def health():
        """Health check endpoint."""
        return {'status': 'healthy', 'version': '1.0.0'}

    # Log configuration
    logger.info("Flask app created")
    logger.info(f"Configuration: {Config.get_summary()}")

    # Validate configuration
    errors = Config.validate()
    if errors:
        logger.warning(f"Configuration warnings: {errors}")

    return app
