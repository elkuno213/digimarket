"""Tests for the trusted local administrator onboarding command."""

import pytest
from flask import Flask
from werkzeug.security import check_password_hash, generate_password_hash

from app.auth import service as auth_service
from app.extensions import db
from app.models.user import User


def test_onboard_administrator_creates_a_normalized_hashed_admin(app: Flask) -> None:
    """Create the first administrator with normalized fields and a password hash."""
    admin = auth_service.onboard_administrator(" Admin@Example.COM ", " Demo Admin ", "eight-char")

    assert admin.email == "admin@example.com"
    assert admin.nom == "Demo Admin"
    assert admin.role == "admin"
    assert check_password_hash(admin.password_hash, "eight-char")


def test_onboard_administrator_refuses_a_second_admin_after_clients_exist(app: Flask) -> None:
    """Allow existing clients but preserve the single-admin onboarding boundary."""
    db.session.add(
        User(
            email="client@example.com",
            nom="Client",
            password_hash=generate_password_hash("eight-char"),
            role="client",
        )
    )
    db.session.commit()
    auth_service.onboard_administrator("first@example.com", "First Admin", "eight-char")

    with pytest.raises(
        auth_service.AdministratorAlreadyExistsError,
        match="administrator already exists",
    ):
        auth_service.onboard_administrator("second@example.com", "Second Admin", "eight-char")

    statement = db.select(User).where(User.email == "second@example.com")
    assert db.session.scalar(statement) is None


def test_onboard_administrator_reports_a_duplicate_client_email(app: Flask) -> None:
    """Keep the normal duplicate-email contract when no administrator exists yet."""
    db.session.add(
        User(
            email="client@example.com",
            nom="Client",
            password_hash=generate_password_hash("eight-char"),
            role="client",
        )
    )
    db.session.commit()

    with pytest.raises(auth_service.DuplicateEmailError, match="account already exists"):
        auth_service.onboard_administrator("client@example.com", "Demo Admin", "eight-char")

    assert db.session.scalar(db.select(User).where(User.role == "admin")) is None


def test_onboard_administrator_leaves_pending_work_after_invalid_input(app: Flask) -> None:
    """Validate before a transaction so invalid input does not discard pending work."""
    pending_client = User(
        email="client@example.com",
        nom="Client",
        password_hash=generate_password_hash("eight-char"),
        role="client",
    )
    db.session.add(pending_client)

    with pytest.raises(auth_service.ValidationError, match="Email address is invalid"):
        auth_service.onboard_administrator("not-an-email", "Demo Admin", "eight-char")

    db.session.commit()
    assert db.session.scalar(db.select(User).where(User.email == pending_client.email)) is not None
    assert db.session.scalar(db.select(User).where(User.role == "admin")) is None

    administrator = auth_service.onboard_administrator(
        "admin@example.com", "Demo Admin", "eight-char"
    )

    assert administrator.email == "admin@example.com"


def test_onboard_command_uses_environment_credentials(
    app: Flask, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Read the trusted CLI inputs from environment variables and report only the email."""
    monkeypatch.setenv("ADMIN_EMAIL", " Admin@Example.COM ")
    monkeypatch.setenv("ADMIN_NAME", " Demo Admin ")
    monkeypatch.setenv("ADMIN_PASSWORD", "eight-char")

    result = app.test_cli_runner().invoke(args=["onboard"])

    assert result.exit_code == 0
    assert result.output == "Administrator onboarded: admin@example.com\n"


def test_onboard_command_reports_invalid_environment_values(
    app: Flask, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Return the shared public validation message for malformed CLI inputs."""
    monkeypatch.setenv("ADMIN_EMAIL", "invalid-email")
    monkeypatch.setenv("ADMIN_NAME", "Demo Admin")
    monkeypatch.setenv("ADMIN_PASSWORD", "eight-char")

    result = app.test_cli_runner().invoke(args=["onboard"])

    assert result.exit_code != 0
    assert result.output == "Error: Email address is invalid.\n"


def test_onboard_command_reports_when_an_administrator_already_exists(
    app: Flask, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Expose the protected one-administrator boundary as a clear CLI error."""
    monkeypatch.setenv("ADMIN_EMAIL", "first@example.com")
    monkeypatch.setenv("ADMIN_NAME", "First Admin")
    monkeypatch.setenv("ADMIN_PASSWORD", "eight-char")
    runner = app.test_cli_runner()

    assert runner.invoke(args=["onboard"]).exit_code == 0

    monkeypatch.setenv("ADMIN_EMAIL", "second@example.com")
    result = runner.invoke(args=["onboard"])

    assert result.exit_code != 0
    assert "Error: An administrator already exists." in result.output
