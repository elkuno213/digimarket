"""Flask application factory for DigiMarket."""

from collections.abc import Mapping
from dataclasses import asdict
from typing import Any

from flask import Flask, Response, jsonify
from werkzeug.exceptions import HTTPException

from app import extensions
from app.auth.authorization import register_jwt_error_handlers
from app.auth.routes import auth_blueprint
from app.config import Config
from app.products.routes import products_blueprint


def create_app(config_override: Mapping[str, Any] | None = None) -> Flask:
    """Create the DigiMarket Flask application.

    Args:
        config_override (Mapping[str, Any] | None): Optional settings applied only to this app.

    Returns:
        Flask: An application configured from the environment.
    """
    app = Flask(__name__)

    # Load the application's settings from the environment, then apply any test overrides.
    app.config.from_mapping(asdict(Config.from_environment()))
    if config_override is not None:
        app.config.from_mapping(config_override)

    # Register extensions, blueprints, and error handlers after the app has loaded its settings.
    register_extensions(app)
    register_blueprints(app)
    register_error_handlers(app)

    return app


def register_extensions(app: Flask) -> None:
    """Bind unbound extension objects after the application has loaded its settings."""
    extensions.db.init_app(app)
    extensions.jwt.init_app(app)
    register_jwt_error_handlers()


def register_blueprints(app: Flask) -> None:
    """Attach every feature's recorded routes to the application."""
    app.register_blueprint(auth_blueprint, url_prefix="/api/auth")
    app.register_blueprint(products_blueprint, url_prefix="/api/produits")


def register_error_handlers(app: Flask) -> None:
    """Register the API-wide JSON error response handlers."""

    @app.errorhandler(HTTPException)
    def on_http_exception(error: HTTPException) -> tuple[Response, int]:
        """Return a JSON response for Flask HTTP errors."""
        return jsonify({"error": error.description}), error.code or 500

    @app.errorhandler(Exception)
    def on_unexpected_exception(_: Exception) -> tuple[Response, int]:
        """Return a non-leaking JSON response for unexpected errors."""
        return jsonify({"error": "Internal server error."}), 500
