"""Tests for DigiMarket authentication routes."""

from collections.abc import Mapping
from datetime import UTC, datetime

import pytest
from flask import Flask
from flask.testing import FlaskClient
from flask_jwt_extended import decode_token
from werkzeug.security import check_password_hash

from app.auth import service as auth_service
from app.extensions import db
from app.models.user import User


def test_login_returns_a_token_for_normalized_admin_credentials(
    app: Flask, client: FlaskClient, admin_user: User
) -> None:
    """Return a token that preserves a normalized administrator identity and role.

    The request deliberately uses an uppercase email. This keeps email normalization
    and the JWT's public claims in one end-to-end authentication test.
    """
    # An uppercase version proves login normalizes the supplied email before lookup.
    response = client.post(
        "/api/auth/login",
        json={
            "email": admin_user.email.upper(),
            "mot_de_passe": "correct-password",
        },
    )

    # Make sure login succeeds, returns only a token, and the token decodes to the expected identity
    # and role.
    assert response.status_code == 200
    body = response.get_json()
    assert isinstance(body, Mapping)
    assert set(body) == {"access_token"}
    assert isinstance(body["access_token"], str)

    # Token decoding needs the Flask app context because it uses the configured JWT secret.
    with app.app_context():
        decoded_token = decode_token(body["access_token"])

    # `sub` identifies the authenticated user; the role supports future authorization checks.
    assert decoded_token["sub"] == str(admin_user.id)
    assert decoded_token["role"] == "admin"


def test_login_returns_the_same_error_for_unknown_and_invalid_credentials(
    client: FlaskClient, admin_user: User
) -> None:
    """Return the same public error for an unknown account and a wrong password.

    Matching responses prevent a caller from discovering which email addresses
    already have an account.
    """
    # The first request has no matching account; the second has a wrong secret for a real account.
    unknown_email_response = client.post(
        "/api/auth/login",
        json={
            "email": "unknown@example.com",
            "mot_de_passe": "correct-password",
        },
    )
    wrong_password_response = client.post(
        "/api/auth/login",
        json={
            "email": admin_user.email,
            "mot_de_passe": "wrong-password",
        },
    )

    assert unknown_email_response.status_code == 401
    assert wrong_password_response.status_code == 401
    assert unknown_email_response.get_json() == wrong_password_response.get_json()
    assert unknown_email_response.get_json() == {"error": "Invalid email or password."}


def test_login_returns_bad_request_for_a_malformed_request(client: FlaskClient) -> None:
    """Reject a valid JSON value that is not the object required by the login API."""
    # A JSON array is syntactically valid, but it cannot provide named credential fields.
    response = client.post("/api/auth/login", json=["not", "an", "object"])

    assert response.status_code == 400
    body = response.get_json()
    assert isinstance(body, Mapping)
    assert isinstance(body["error"], str)


def test_register_creates_a_normalized_client_account(client: FlaskClient) -> None:
    """Create a normalized client account without exposing or storing a raw password.

    This combines the registration endpoint's main public guarantees: input cleanup,
    fixed client role, safe response serialization, and password hashing.
    """
    # The requested admin role must be ignored: public registration creates clients only.
    response = client.post(
        "/api/auth/register",
        json={
            "email": " Alice@Example.COM ",
            "nom": " Alice ",
            "mot_de_passe": "eight-char",
            "role": "admin",
        },
    )

    assert response.status_code == 201
    body = response.get_json()
    assert isinstance(body, Mapping)
    assert body["email"] == "alice@example.com"
    assert body["nom"] == "Alice"
    assert body["role"] == "client"
    assert "password_hash" not in body
    assert "mot_de_passe" not in body
    assert set(body) == {"id", "email", "nom", "role", "date_creation"}
    date_creation = body["date_creation"]
    assert isinstance(date_creation, str)
    assert datetime.fromisoformat(date_creation).tzinfo == UTC

    # The HTTP response is safe, but persistence must still contain a verifiable password hash.
    user = db.session.scalar(db.select(User).filter_by(email="alice@example.com"))

    assert user is not None
    assert check_password_hash(user.password_hash, "eight-char")


@pytest.mark.parametrize(
    "payload",
    [
        {"email": "alice@example.com", "mot_de_passe": "eight-char"},
        {"email": "invalid-email", "nom": "Alice", "mot_de_passe": "eight-char"},
        {"email": "alice@example.com", "nom": "Alice", "mot_de_passe": "short"},
    ],
    ids=[
        "missing_nom",
        "invalid_email",
        "short_password",
    ],
)
def test_register_returns_bad_request_for_invalid_payloads(
    client: FlaskClient, payload: object
) -> None:
    """Reject representative registration failures with a JSON client error.

    Parameterization keeps one shared response contract while covering a missing
    name, malformed email, and password shorter than the required minimum.
    """
    # Each parameter supplies one invalid public-input category.
    response = client.post("/api/auth/register", json=payload)

    assert response.status_code == 400
    assert isinstance(response.get_json(), Mapping)
    assert isinstance(response.get_json()["error"], str)


def test_register_rejects_a_duplicate_normalized_email(client: FlaskClient) -> None:
    """Reject a second account whose differently formatted email normalizes identically."""
    # Create the canonical account first so the next request can exercise the uniqueness rule.
    first_response = client.post(
        "/api/auth/register",
        json={
            "email": "Alice@Example.com",
            "nom": "Alice",
            "mot_de_passe": "eight-char",
        },
    )
    # Whitespace and lowercase formatting still represent the same email address.
    second_response = client.post(
        "/api/auth/register",
        json={
            "email": " alice@example.com ",
            "nom": "Alice Second",
            "mot_de_passe": "eight-char",
        },
    )

    assert first_response.status_code == 201
    assert second_response.status_code == 409
    assert isinstance(second_response.get_json(), Mapping)
    assert isinstance(second_response.get_json()["error"], str)


def test_register_recovers_after_a_unique_constraint_race(
    client: FlaskClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Recover the SQLAlchemy session after a database uniqueness race.

    The test simulates two requests passing the application-level duplicate check.
    The database remains the authoritative protection, and rollback must leave the
    session usable for the next request.
    """
    # Step 1: persist Alice exactly as the first of two concurrent requests would do.
    first_response = client.post(
        "/api/auth/register",
        json={
            "email": "alice@example.com",
            "nom": "Alice",
            "mot_de_passe": "eight-char",
        },
    )
    # Step 2: replace the real lookup only for this test. register_user() will now receive None
    # from find_user_by_email(), although Alice is already in the database.
    # This simulates a second request that performed its pre-check before Alice committed.
    monkeypatch.setattr(auth_service, "find_user_by_email", lambda _email: None)

    # Step 3: the stale pre-check allows this duplicate insert attempt to reach commit().
    # SQLite's unique email constraint—not the mocked Python pre-check—must reject it.
    raced_response = client.post(
        "/api/auth/register",
        json={
            "email": "alice@example.com",
            "nom": "Alice Duplicate",
            "mot_de_passe": "eight-char",
        },
    )
    # Step 4: after the failed commit, a rollback must make the session usable again.
    # Registering Bob is the observable proof that the session was repaired.
    following_response = client.post(
        "/api/auth/register",
        json={
            "email": "bob@example.com",
            "nom": "Bob",
            "mot_de_passe": "eight-char",
        },
    )

    # First request succeeds; the simulated concurrent duplicate becomes a public conflict.
    assert first_response.status_code == 201
    assert raced_response.status_code == 409
    assert isinstance(raced_response.get_json(), Mapping)
    assert isinstance(raced_response.get_json()["error"], str)
    # Without rollback(), this request would fail because SQLAlchemy keeps a failed session state.
    assert following_response.status_code == 201
    assert db.session.scalar(db.select(User).filter_by(email="bob@example.com")) is not None
