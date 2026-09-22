"""Behavioral tests for product service operations."""

import pytest
from flask import Flask

from app.extensions import db
from app.models.product import Product
from app.products.service import (
    ProductData,
    ProductNotFoundError,
    ValidationError,
    create_product,
    delete_product,
    get_product,
    list_products,
    update_product,
    validate_product_payload,
)


def test_validate_product_payload_normalizes_valid_values() -> None:
    """Strip text values and convert a valid JSON price to a float."""
    payload = {
        "nom": " Keyboard ",
        "description": " Mechanical ",
        "categorie": " Accessories ",
        "prix": 89,
        "quantite_stock": 3,
    }

    assert validate_product_payload(payload) == ProductData(
        nom="Keyboard",
        description="Mechanical",
        categorie="Accessories",
        prix=89.0,
        quantite_stock=3,
    )


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        (
            {
                "nom": "Keyboard",
                "description": "Mechanical",
                "categorie": "Accessories",
                "prix": 0,
                "quantite_stock": 3,
            },
            "prix must be a positive number.",
        ),
        (
            {
                "nom": "Keyboard",
                "description": "Mechanical",
                "categorie": "Accessories",
                "prix": 89,
                "quantite_stock": -1,
            },
            "quantite_stock must be a non-negative integer.",
        ),
    ],
)
def test_validate_product_payload_rejects_invalid_numbers(
    payload: dict[str, int | str], message: str
) -> None:
    """Reject non-positive prices and negative stock counts."""
    with pytest.raises(ValidationError, match=message):
        validate_product_payload(payload)


def test_validate_product_payload_rejects_an_unrepresentable_negative_price() -> None:
    """Report the public validation error for a huge negative integer price."""
    payload = {
        "nom": "Keyboard",
        "description": "Mechanical",
        "categorie": "Accessories",
        "prix": -(10**400),
        "quantite_stock": 3,
    }

    with pytest.raises(ValidationError) as error:
        validate_product_payload(payload)

    assert str(error.value) == "prix must be a positive number."


def test_validate_product_payload_enforces_the_sqlite_stock_integer_boundary() -> None:
    """Accept the largest SQLite stock value and reject the next integer."""
    payload = {
        "nom": "Keyboard",
        "description": "Mechanical",
        "categorie": "Accessories",
        "prix": 89,
        "quantite_stock": 2**63 - 1,
    }

    assert validate_product_payload(payload).quantite_stock == 2**63 - 1

    payload["quantite_stock"] = 2**63
    with pytest.raises(ValidationError) as error:
        validate_product_payload(payload)

    assert str(error.value) == "quantite_stock must be a non-negative integer."


def test_create_product_rejects_stock_that_cannot_fit_in_sqlite(app: Flask) -> None:
    """Reject direct service data that cannot be stored in SQLite's integer column."""
    data = ProductData(
        nom="Keyboard",
        description="Mechanical",
        categorie="Accessories",
        prix=89.0,
        quantite_stock=2**63,
    )

    with pytest.raises(ValidationError) as error:
        create_product(data)

    assert str(error.value) == "quantite_stock must be a non-negative integer."
    assert list_products(None) == []


def test_list_products_matches_literal_text_across_product_fields(app: Flask) -> None:
    """Return ordered matches from names, descriptions, and categories."""
    keyboard = Product(
        nom="Keyboard",
        description="Mechanical key switches",
        categorie="Accessories",
        prix=89.0,
        quantite_stock=3,
    )
    mouse = Product(
        nom="Mouse",
        description="Ergonomic grip",
        categorie="Peripherals",
        prix=45.0,
        quantite_stock=4,
    )
    cable = Product(
        nom="Cable",
        description="Braided USB cable",
        categorie="Accessories",
        prix=12.0,
        quantite_stock=10,
    )
    db.session.add_all([keyboard, mouse, cable])
    db.session.commit()

    assert list_products("key") == [keyboard]
    assert list_products("ergonomic") == [mouse]
    assert list_products("accessories") == [keyboard, cable]
    assert list_products("%") == []


def test_product_lifecycle_replaces_editable_values_and_preserves_creation_date(app: Flask) -> None:
    """Persist, replace, reload, and delete a product through the service."""
    created = create_product(
        ProductData(
            nom="Keyboard",
            description="Mechanical",
            categorie="Accessories",
            prix=89.0,
            quantite_stock=3,
        )
    )
    product_id = created.id
    db.session.remove()
    original_product = db.session.get(Product, product_id)

    assert original_product is not None
    original_creation_date = original_product.date_creation

    update_product(
        product_id,
        ProductData(
            nom="Mouse",
            description="Ergonomic",
            categorie="Peripherals",
            prix=45.0,
            quantite_stock=4,
        ),
    )
    db.session.remove()
    reloaded_product = db.session.get(Product, product_id)

    assert reloaded_product is not None
    assert (
        reloaded_product.nom,
        reloaded_product.description,
        reloaded_product.categorie,
        reloaded_product.prix,
        reloaded_product.quantite_stock,
        reloaded_product.date_creation,
    ) == ("Mouse", "Ergonomic", "Peripherals", 45.0, 4, original_creation_date)

    delete_product(product_id)
    db.session.remove()

    assert db.session.get(Product, product_id) is None


def test_create_product_recovers_the_session_after_an_ordinary_commit_error(
    app: Flask, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Roll back a failed write so a later product creation can succeed."""
    data = ProductData(
        nom="Keyboard",
        description="Mechanical",
        categorie="Accessories",
        prix=89.0,
        quantite_stock=3,
    )
    original_commit = db.session.commit

    def fail_commit() -> None:
        raise OverflowError("simulated SQLite conversion failure")

    monkeypatch.setattr(db.session, "commit", fail_commit)
    with pytest.raises(OverflowError, match="simulated SQLite conversion failure"):
        create_product(data)

    monkeypatch.setattr(db.session, "commit", original_commit)

    assert list_products(None) == []
    assert create_product(data).id is not None


def test_get_product_raises_for_an_unknown_identifier(app: Flask) -> None:
    """Raise the domain error when no product has the requested identifier."""
    with pytest.raises(ProductNotFoundError, match="Product not found"):
        get_product(999)
