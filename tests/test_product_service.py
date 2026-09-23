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
    validate_product,
)


def test_validate_product_normalizes_payload() -> None:
    """Strip text values and convert a valid JSON price to a float."""
    payload = {
        "nom": " Keyboard ",
        "description": " Mechanical ",
        "categorie": " Accessories ",
        "prix": 89,
        "quantite_stock": 3,
    }

    assert validate_product(payload) == ProductData(
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
def test_validate_product_rejects_invalid_values(
    payload: dict[str, int | str], message: str
) -> None:
    """Reject non-positive prices and negative stock counts."""
    with pytest.raises(ValidationError, match=message):
        validate_product(payload)


def test_list_products_matches_catalogue_fields(app: Flask) -> None:
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


def test_product_lifecycle(app: Flask) -> None:
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


def test_get_product_rejects_unknown_id(app: Flask) -> None:
    """Raise the domain error when no product has the requested identifier."""
    with pytest.raises(ProductNotFoundError, match="Product not found"):
        get_product(999)
