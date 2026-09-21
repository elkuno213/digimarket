"""Tests for Flask application factory composition."""

from pathlib import Path

from flask import Flask
from pytest import MonkeyPatch

from app import create_app, db, jwt


def test_factory_returns_app_with_module_extensions(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    """The factory returns a Flask app using the shared extension instances."""
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "test.db"))
    monkeypatch.setenv("JWT_SECRET_KEY", "test-jwt-secret")
    app = create_app()

    assert isinstance(app, Flask)
    assert app.extensions["sqlalchemy"] is db
    assert app.extensions["flask-jwt-extended"] is jwt


def test_factory_applies_configuration_override_to_returned_app(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    """An override configures only the application returned by the factory."""
    database_url = f"sqlite:///{tmp_path / 'test.db'}"
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "test.db"))
    monkeypatch.setenv("JWT_SECRET_KEY", "environment-test-jwt-secret")

    app = create_app(
        {
            "SQLALCHEMY_DATABASE_URI": database_url,
            "TESTING": True,
            "JWT_SECRET_KEY": "test-jwt-secret",
        }
    )

    assert app.config["SQLALCHEMY_DATABASE_URI"] == database_url
    assert app.config["TESTING"] is True
    assert app.config["JWT_SECRET_KEY"] == "test-jwt-secret"
