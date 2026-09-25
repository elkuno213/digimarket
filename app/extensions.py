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
def _configure_sqlite_connection(dbapi_connection: object, _: object) -> None:
    """Enable foreign keys and install Unicode search on each SQLite connection."""
    # Configure only SQLite; another SQLAlchemy engine does not expose these APIs.
    if isinstance(dbapi_connection, sqlite3.Connection):
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("PRAGMA foreign_keys = ON")
        finally:
            cursor.close()
        dbapi_connection.create_function(
            "unicode_casefold",
            1,
            _unicode_casefold,
            deterministic=True,
        )


# These objects are not attached to a Flask application until create_app() calls init_app().
db = SQLAlchemy()
jwt = JWTManager()
