"""Tests for application configuration defaults and environment overrides."""

import pytest
from conftest import TEST_JWT_SECRET
from pytest import MonkeyPatch

from app.config import Config


@pytest.mark.parametrize(
    ("setting_name", "invalid_value"),
    [
        ("DATABASE_PATH", None),
        ("DATABASE_PATH", ""),
        ("JWT_SECRET_KEY", None),
        ("JWT_SECRET_KEY", ""),
    ],
)
def test_environment_config_rejects_missing_or_empty_required_settings(
    monkeypatch: MonkeyPatch, setting_name: str, invalid_value: str | None
) -> None:
    """Configuration rejects absent and empty values for both required settings."""
    # Start valid, then remove or empty one required setting for each parameter.
    monkeypatch.setenv("DATABASE_PATH", "/tmp/digimarket-test.db")
    monkeypatch.setenv("JWT_SECRET_KEY", TEST_JWT_SECRET)
    if invalid_value is None:
        monkeypatch.delenv(setting_name)
    else:
        monkeypatch.setenv(setting_name, invalid_value)

    # Configuration must fail before Flask receives incomplete runtime settings.
    with pytest.raises(RuntimeError, match=setting_name):
        Config.from_environment()


def test_environment_path_and_jwt_configure_the_application(monkeypatch: MonkeyPatch) -> None:
    """Explicit path and JWT values configure their matching settings."""
    # Set both required values, then build immutable configuration from the environment.
    database_path = "/tmp/digimarket-test.db"
    jwt_secret = TEST_JWT_SECRET
    monkeypatch.setenv("DATABASE_PATH", database_path)
    monkeypatch.setenv("JWT_SECRET_KEY", jwt_secret)

    config = Config.from_environment()

    # Check path conversion and JWT pass-through independently.
    assert config.SQLALCHEMY_DATABASE_URI == f"sqlite:///{database_path}"
    assert config.JWT_SECRET_KEY == jwt_secret
