"""Tests for public product catalogue routes."""

from collections.abc import Mapping

from flask.testing import FlaskClient

from app.extensions import db
from app.models.product import Product


def test_catalogue_lists_and_filters_products_without_authentication(client: FlaskClient) -> None:
    """Return ID-ordered products and filter their public catalogue by text."""
    keyboard = Product(
        nom="Keyboard",
        description="Mechanical keyboard",
        categorie="Accessories",
        prix=99.99,
        quantite_stock=10,
    )
    mouse = Product(
        nom="Mouse",
        description="Ergonomic mouse",
        categorie="Accessories",
        prix=49.99,
        quantite_stock=20,
    )
    db.session.add_all([keyboard, mouse])
    db.session.commit()

    catalogue_response = client.get("/api/produits")
    matching_response = client.get("/api/produits?q=ERGONOMIC")
    empty_response = client.get("/api/produits?q=no-match")

    assert catalogue_response.status_code == 200
    catalogue = catalogue_response.get_json()
    assert isinstance(catalogue, list)
    assert [product["nom"] for product in catalogue] == ["Keyboard", "Mouse"]
    assert matching_response.status_code == 200
    assert matching_response.get_json() == [mouse.to_dict()]
    assert empty_response.status_code == 200
    assert empty_response.get_json() == []


def test_catalogue_returns_product_detail_or_not_found_error(client: FlaskClient) -> None:
    """Return a public product representation or the documented missing-product error."""
    product = Product(
        nom="Keyboard",
        description="Mechanical keyboard",
        categorie="Accessories",
        prix=99.99,
        quantite_stock=10,
    )
    db.session.add(product)
    db.session.commit()

    detail_response = client.get(f"/api/produits/{product.id}")
    missing_response = client.get("/api/produits/999")
    largest_id_response = client.get(f"/api/produits/{2**63 - 1}")
    unrepresentable_id_response = client.get(f"/api/produits/{2**63}")

    assert detail_response.status_code == 200
    body = detail_response.get_json()
    assert isinstance(body, Mapping)
    assert body == product.to_dict()
    assert missing_response.status_code == 404
    assert missing_response.get_json() == {"error": "Product not found."}
    assert largest_id_response.status_code == 404
    assert largest_id_response.get_json() == {"error": "Product not found."}
    assert unrepresentable_id_response.status_code == 404
    assert unrepresentable_id_response.get_json() == {"error": "Product not found."}
