"""Unbound Flask extension instances shared by DigiMarket modules."""

import sqlite3

from flask_jwt_extended import JWTManager
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import event
from sqlalchemy.engine import Engine


def _unicode_casefold(value: str | None) -> str | None:
    """Return the Unicode case-folded SQLite text value."""
    return value.casefold() if value is not None else None


@event.listens_for(Engine, "connect")
def _register_sqlite_casefold_function(dbapi_connection: object, _: object) -> None:
    """Install the Unicode search function on each SQLite connection."""
    # Register only for SQLite; another SQLAlchemy engine does not expose this API.
    if isinstance(dbapi_connection, sqlite3.Connection):
        dbapi_connection.create_function(
            "unicode_casefold",
            1,
            _unicode_casefold,
            deterministic=True,
        )


# These objects are not attached to a Flask application until create_app() calls init_app().
db = SQLAlchemy()
jwt = JWTManager()
