"""Application configuration."""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Self


@dataclass(frozen=True)
class Config:
    """Immutable Flask settings for the DigiMarket application."""

    SQLALCHEMY_DATABASE_URI: str  # Address of the database to connect to.
    SQLALCHEMY_TRACK_MODIFICATIONS: bool  # Whether to track object modifications and emit signals.
    JWT_SECRET_KEY: str  # secret key used to sign JWTs for authentication
    TESTING: bool = False  # Whether the application is running in a test context.

    @classmethod
    def from_environment(cls) -> Self:
        """Build configuration from explicit environment settings."""
        # DATABASE_PATH is required; flag an error when it is missing or empty.
        database_path = os.environ.get("DATABASE_PATH")
        if not database_path:
            raise RuntimeError("Set DATABASE_PATH before starting DigiMarket.")
        # Build the SQLite connection URL.
        database_uri = f"sqlite:///{Path(database_path).expanduser().resolve()}"

        # JWT_SECRET_KEY signs every access token and must remain stable across restarts.
        jwt_secret = os.environ.get("JWT_SECRET_KEY")
        if not jwt_secret:
            raise RuntimeError("Set JWT_SECRET_KEY before starting DigiMarket.")

        return cls(
            SQLALCHEMY_DATABASE_URI=database_uri,
            SQLALCHEMY_TRACK_MODIFICATIONS=False,
            JWT_SECRET_KEY=jwt_secret,
        )
