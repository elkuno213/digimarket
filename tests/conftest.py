"""Shared pytest fixtures for isolated application tests."""

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from flask import Flask
from flask.testing import FlaskClient
from werkzeug.security import generate_password_hash

from app import create_app
from app.extensions import db
from app.models.user import User

TEST_JWT_SECRET = "test-jwt-secret-at-least-thirty-two-bytes-long"


@pytest.fixture
def app(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Flask]:
    """Provide an application backed by a temporary SQLite database."""
    database_path = tmp_path / "test.db"
    monkeypatch.setenv("DATABASE_PATH", str(database_path))
    monkeypatch.setenv("JWT_SECRET_KEY", TEST_JWT_SECRET)
    app = create_app(
        {
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{database_path}",
            "TESTING": True,
            "JWT_SECRET_KEY": TEST_JWT_SECRET,
        }
    )

    # Create the database schema, yield the app for testing and then drop the schema to clean up.
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app: Flask) -> FlaskClient:
    """Provide a Flask test client."""
    return app.test_client()


@pytest.fixture
def admin_user(app: Flask) -> User:
    """Provide a persisted administrator with a known test password."""
    user = User(
        email="admin@example.com",
        password_hash=generate_password_hash("correct-password"),
        nom="Administrator",
        role="admin",
        date_creation=datetime.now(UTC),
    )
    db.session.add(user)
    db.session.commit()
    return user
