"""Tests for Flask application factory composition."""

from importlib.util import find_spec
from pathlib import Path

from conftest import TEST_JWT_SECRET
from flask import Flask
from pytest import MonkeyPatch

import app
from app import create_app
from app.extensions import db, jwt


def test_extensions_have_a_dedicated_module() -> None:
    """Keep shared Flask extensions outside the application factory module."""
    # Check imports expose the extension module without leaking its instances from app.
    assert find_spec("app.extensions") is not None
    assert not hasattr(app, "db")


def test_factory_returns_app_with_module_extensions(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    """The factory returns a Flask app using the shared extension instances."""
    # Supply required environment values, then create one independent application.
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "test.db"))
    monkeypatch.setenv("JWT_SECRET_KEY", TEST_JWT_SECRET)
    app = create_app()

    # Verify framework type, shared extension identity, and expected feature registration.
    assert isinstance(app, Flask)
    assert app.extensions["sqlalchemy"] is db
    assert app.extensions["flask-jwt-extended"] is jwt
    assert "orders" in app.blueprints


def test_factory_applies_configuration_override_to_returned_app(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    """An override configures only the application returned by the factory."""
    # Set normal configuration first so the override has a realistic base application.
    database_url = f"sqlite:///{tmp_path / 'test.db'}"
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "test.db"))
    monkeypatch.setenv("JWT_SECRET_KEY", TEST_JWT_SECRET)

    app = create_app(
        {
            "SQLALCHEMY_DATABASE_URI": database_url,
            "TESTING": True,
            "JWT_SECRET_KEY": TEST_JWT_SECRET,
        }
    )

    # Confirm explicit overrides win for this factory result.
    assert app.config["SQLALCHEMY_DATABASE_URI"] == database_url
    assert app.config["TESTING"] is True
    assert app.config["JWT_SECRET_KEY"] == TEST_JWT_SECRET
