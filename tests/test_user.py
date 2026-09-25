"""Tests for the user SQLAlchemy model."""

from datetime import UTC, datetime

from flask import Flask

from app.extensions import db
from app.models.user import User


def test_persisted_user_serializes_naive_sqlite_datetime_as_utc(app: Flask) -> None:
    """Serialize a SQLite-reloaded user with an explicit UTC timestamp."""
    assert app.config["TESTING"] is True

    # Create a user with a specific UTC timestamp.
    user = User(
        email="member@example.com",
        password_hash="hashed-secret",
        nom="Ada Lovelace",
        role="client",
        date_creation=datetime(2026, 9, 21, 12, 30, tzinfo=UTC),
    )

    assert user.to_dict()["date_creation"] == "2026-09-21T12:30:00+00:00"

    # Save the user, then clear session state before a SQLite reload.
    db.session.add(user)
    db.session.commit()
    user_id = user.id
    assert user_id > 0
    db.session.remove()

    # Reload the user and check persisted public fields plus private-password exclusion.
    persisted_user = db.session.get(User, user_id)

    assert persisted_user is not None
    assert persisted_user.id == user_id
    assert persisted_user.email == "member@example.com"
    assert persisted_user.nom == "Ada Lovelace"
    assert persisted_user.role == "client"
    assert persisted_user.date_creation.tzinfo is None

    serialized_user = persisted_user.to_dict()

    assert "password_hash" not in serialized_user
    assert serialized_user == {
        "id": user_id,
        "email": "member@example.com",
        "nom": "Ada Lovelace",
        "role": "client",
        "date_creation": "2026-09-21T12:30:00+00:00",
    }
