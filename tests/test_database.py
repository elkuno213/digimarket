"""Smoke tests for database connection isolation and fixture safety."""

from hashlib import sha256
from pathlib import Path
from shutil import copyfile

from conftest import TEST_JWT_SECRET
from flask import Flask
from pytest import MonkeyPatch
from sqlalchemy import func, inspect, text
from werkzeug.security import check_password_hash

from app import create_app
from app.auth.service import onboard_administrator
from app.extensions import db
from app.models.order import Order
from app.models.order_item import OrderItem
from app.models.product import Product
from app.models.user import User

_DATABASE_DIRECTORY = Path(__file__).resolve().parents[1]
_REQUIRED_TABLE_COLUMNS = {
    "user": {"id", "email", "password_hash", "nom", "role", "date_creation"},
    "product": {"id", "nom", "description", "categorie", "prix", "quantite_stock", "date_creation"},
    "order": {"id", "utilisateur_id", "date_commande", "adresse_livraison", "statut"},
    "order_item": {"id", "commande_id", "produit_id", "quantite", "prix_unitaire"},
}


def _sidecar_paths(database_path: Path) -> tuple[Path, Path]:
    """Return SQLite's optional write-ahead-log files for one database."""
    return (
        database_path.with_name(f"{database_path.name}-wal"),
        database_path.with_name(f"{database_path.name}-shm"),
    )


def _create_app_for_database(
    monkeypatch: MonkeyPatch,
    database_path: Path,
    *,
    read_only: bool = False,
) -> Flask:
    """Create a test application configured explicitly for one SQLite database."""
    # Set factory-required environment values before optionally switching to read-only SQLite.
    monkeypatch.setenv("DATABASE_PATH", str(database_path))
    monkeypatch.setenv("JWT_SECRET_KEY", TEST_JWT_SECRET)
    database_uri = f"sqlite:///{database_path}"
    if read_only:
        database_uri = f"sqlite:///file:{database_path.as_posix()}?mode=ro&uri=true"
    return create_app(
        {
            "JWT_SECRET_KEY": TEST_JWT_SECRET,
            "SQLALCHEMY_DATABASE_URI": database_uri,
            "TESTING": True,
        }
    )


def _count(model: type[User] | type[Product] | type[Order] | type[OrderItem]) -> int:
    """Return one model's persisted record count using SQLAlchemy's select API."""
    return db.session.scalar(db.select(func.count()).select_from(model)) or 0


def test_temporary_database_is_connected_independently(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    """A temporary SQLite override connects outside tracked database fixtures."""
    # Create an app for a fresh path, then prove its connection can execute SQL.
    database_path = tmp_path / "test.db"
    app = _create_app_for_database(monkeypatch, database_path)

    with app.app_context():
        assert db.session.execute(text("SELECT 1")).scalar_one() == 1

    assert database_path.exists()


def test_sqlite_connections_enforce_foreign_keys(app: Flask) -> None:
    """Every application-managed SQLite connection enforces declared relationships."""
    assert db.session.scalar(text("PRAGMA foreign_keys")) == 1


def test_supplied_database_is_readable_empty_schema_without_file_changes(
    monkeypatch: MonkeyPatch,
) -> None:
    """The tracked blank database supports read-only schema inspection."""
    # Snapshot the supplied file before read-only schema and empty-table checks.
    database_path = _DATABASE_DIRECTORY / "digimarket-empty.db"
    before_hash = sha256(database_path.read_bytes()).digest()
    sidecar_paths = _sidecar_paths(database_path)
    assert not any(path.exists() for path in sidecar_paths)
    app = _create_app_for_database(monkeypatch, database_path, read_only=True)

    # Inspect tables without writing records or SQLite sidecar files.
    with app.app_context():
        inspector = inspect(db.engine)
        table_names = set(inspector.get_table_names())
        table_columns = {
            table_name: {column["name"] for column in inspector.get_columns(table_name)}
            for table_name in _REQUIRED_TABLE_COLUMNS
        }
        assert db.session.execute(text("PRAGMA integrity_check")).scalar_one() == "ok"
        assert _count(User) == 0
        assert _count(Product) == 0
        assert _count(Order) == 0
        assert _count(OrderItem) == 0

    # Confirm expected schema and exact source bytes remain unchanged.
    assert set(_REQUIRED_TABLE_COLUMNS).issubset(table_names)
    assert table_columns == _REQUIRED_TABLE_COLUMNS
    assert sha256(database_path.read_bytes()).digest() == before_hash
    assert not any(path.exists() for path in sidecar_paths)


def test_supplied_sample_database_contains_coherent_demo_data(
    monkeypatch: MonkeyPatch,
) -> None:
    """The tracked sample database provides usable records for every required entity."""
    database_path = _DATABASE_DIRECTORY / "digimarket.db"
    before_hash = sha256(database_path.read_bytes()).digest()
    sidecar_paths = _sidecar_paths(database_path)
    assert not any(path.exists() for path in sidecar_paths)
    app = _create_app_for_database(monkeypatch, database_path, read_only=True)

    with app.app_context():
        assert db.session.execute(text("PRAGMA foreign_key_check")).all() == []
        administrator = db.session.scalar(
            db.select(User).where(User.email == "admin@digimarket.test")
        )
        client = db.session.scalar(
            db.select(User).where(User.email == "client.one@digimarket.test")
        )
        assert administrator is not None
        assert client is not None

        sample_order = db.session.scalar(db.select(Order).where(Order.utilisateur_id == client.id))
        assert sample_order is not None
        assert administrator.role == "admin"
        assert client.role == "client"
        assert check_password_hash(administrator.password_hash, "admin-demo-password")
        assert check_password_hash(client.password_hash, "client-one-password")
        assert _count(Product) >= 2
        assert _count(OrderItem) >= 1
        assert sample_order.lignes

    assert sha256(database_path.read_bytes()).digest() == before_hash
    assert not any(path.exists() for path in sidecar_paths)


def test_onboarding_a_copied_empty_schema_keeps_the_tracked_fixture_unchanged(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    """Onboarding writes only to a copied blank database, never the tracked schema."""
    # Copy the empty schema, then direct onboarding at the disposable copy.
    source_path = _DATABASE_DIRECTORY / "digimarket-empty.db"
    before_hash = sha256(source_path.read_bytes()).digest()
    database_path = tmp_path / "onboarded.db"
    copyfile(source_path, database_path)
    app = _create_app_for_database(monkeypatch, database_path)

    # Create one administrator only in the copied database.
    with app.app_context():
        administrator = onboard_administrator("admin@example.test", "Demo Admin", "eight-char")
        admins = db.session.scalars(db.select(User).where(User.role == "admin")).all()

    assert administrator.email == "admin@example.test"
    assert [(admin.email, admin.nom, admin.role) for admin in admins] == [
        ("admin@example.test", "Demo Admin", "admin")
    ]
    assert sha256(source_path.read_bytes()).digest() == before_hash


def test_application_registers_onboard_command(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    """The application registers the trusted onboarding command."""
    # Factory registration must expose setup command without executing it.
    app = _create_app_for_database(monkeypatch, tmp_path / "test.db")

    assert "onboard" in app.cli.commands
