"""Tests for the product SQLAlchemy model."""

from datetime import UTC, datetime

from flask import Flask

from app.extensions import db
from app.models.product import Product


def test_persisted_product_serializes_a_sqlite_datetime_as_utc(app: Flask) -> None:
    """Expose every product field and normalize a SQLite-reloaded timestamp."""
    product = Product(
        nom="Mechanical Keyboard",
        description="Hot-swappable switches",
        categorie="Accessories",
        prix=89.99,
        quantite_stock=7,
        date_creation=datetime(2026, 9, 22, 9, 30, tzinfo=UTC),
    )
    db.session.add(product)
    db.session.commit()
    product_id = product.id
    db.session.remove()

    persisted_product = db.session.get(Product, product_id)

    assert persisted_product is not None
    assert persisted_product.date_creation.tzinfo is None
    assert persisted_product.to_dict() == {
        "id": product_id,
        "nom": "Mechanical Keyboard",
        "description": "Hot-swappable switches",
        "categorie": "Accessories",
        "prix": 89.99,
        "quantite_stock": 7,
        "date_creation": "2026-09-22T09:30:00+00:00",
    }
