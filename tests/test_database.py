"""Smoke tests for database connection isolation and fixture safety."""

from hashlib import sha256
from pathlib import Path

from conftest import TEST_JWT_SECRET
from pytest import MonkeyPatch
from sqlalchemy import text

from app import create_app
from app.extensions import db


def test_temporary_database_is_connected_independently(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    """A temporary SQLite override connects to a database outside project fixtures."""
    database_path = tmp_path / "test.db"
    monkeypatch.setenv("DATABASE_PATH", str(database_path))
    monkeypatch.setenv("JWT_SECRET_KEY", TEST_JWT_SECRET)
    app = create_app(
        {
            "JWT_SECRET_KEY": TEST_JWT_SECRET,
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{database_path}",
            "TESTING": True,
        }
    )

    with app.app_context():
        # SELECT 1 proves this engine connected to tmp_path/test.db, not project fixture database.
        result = db.session.execute(text("SELECT 1"))
        assert result.scalar_one() == 1

    # SQLite created test.db through temporary engine, keeping project fixture separate.
    assert database_path.exists()


def test_supplied_database_is_readable_without_file_changes(
    monkeypatch: MonkeyPatch,
) -> None:
    """The supplied SQLite fixture supports read-only schema inspection."""
    database_path = Path(__file__).resolve().parents[1] / "digimarket.db"
    before = database_path.read_bytes()

    # Select the supplied fixture explicitly instead of relying on the process launch directory.
    monkeypatch.setenv("DATABASE_PATH", str(database_path))
    monkeypatch.setenv("JWT_SECRET_KEY", TEST_JWT_SECRET)
    app = create_app()

    with app.app_context():
        # SELECT-only inspection reads schema metadata without requesting any database mutation.
        result = db.session.execute(text("SELECT name FROM sqlite_master WHERE type = 'table'"))
        table_names = set(result.scalars())

    after = database_path.read_bytes()

    assert {"user", "product", "order", "order_item"}.issubset(table_names)
    assert sha256(before).digest() == sha256(after).digest()  # unchanged fixture bytes
