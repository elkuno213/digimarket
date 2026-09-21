"""Flask application factory and extension instances."""

from collections.abc import Mapping
from dataclasses import asdict
from typing import Any

from flask import Flask
from flask_jwt_extended import JWTManager
from flask_sqlalchemy import SQLAlchemy

from app.config import Config

# Extensions are constructed once but bound only by the factory, avoiding global Flask app state.
db = SQLAlchemy()
jwt = JWTManager()


def create_app(config_override: Mapping[str, Any] | None = None) -> Flask:
    """Create the DigiMarket Flask application.

    Args:
        config_override (Mapping[str, Any] | None): Optional settings applied only to this app.

    Returns:
        Flask: An application configured from the environment.
    """
    app = Flask(__name__)

    # Base configuration remains owned by Config so environment defaults stay centralized.
    app.config.from_mapping(asdict(Config.from_environment()))
    # Test overrides affect this returned application without changing environment-derived defaults.
    if config_override is not None:
        app.config.from_mapping(config_override)

    # Bind extensions only after the application's settings have been finalized.
    db.init_app(app)
    jwt.init_app(app)

    return app
