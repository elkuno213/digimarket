"""Tests for public product catalogue routes."""

from collections.abc import Mapping

from flask.testing import FlaskClient

from app.extensions import db
from app.models.product import Product

PRODUCT_PAYLOAD: dict[str, object] = {
    "nom": "Keyboard",
    "description": "Quiet switches",
    "categorie": "Accessories",
    "prix": 89.99,
    "quantite_stock": 4,
}


def test_list_products_returns_public_catalogue(client: FlaskClient) -> None:
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


def test_get_product_returns_detail_or_not_found(client: FlaskClient) -> None:
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

    assert detail_response.status_code == 200
    body = detail_response.get_json()
    assert isinstance(body, Mapping)
    assert body == product.to_dict()
    assert missing_response.status_code == 404
    assert missing_response.get_json() == {"error": "Product not found."}


def test_create_product_requires_administrator(
    client: FlaskClient, client_headers: dict[str, str]
) -> None:
    """Reject missing and non-administrator credentials for product creation."""
    missing_token_response = client.post("/api/produits", json=PRODUCT_PAYLOAD)
    client_response = client.post("/api/produits", json=PRODUCT_PAYLOAD, headers=client_headers)

    assert missing_token_response.status_code == 401
    assert isinstance(missing_token_response.get_json()["error"], str)
    assert client_response.status_code == 403
    assert client_response.get_json() == {"error": "Administrator access is required."}


def test_create_product_rejects_invalid_payload(
    client: FlaskClient, admin_headers: dict[str, str]
) -> None:
    """Reject an invalid administrator product payload before persistence."""
    response = client.post(
        "/api/produits",
        json={**PRODUCT_PAYLOAD, "prix": 0},
        headers=admin_headers,
    )

    assert response.status_code == 400
    assert isinstance(response.get_json()["error"], str)
    assert db.session.scalar(db.select(Product)) is None


def test_administrator_product_lifecycle(
    client: FlaskClient, admin_headers: dict[str, str]
) -> None:
    """Create, fully replace, and delete a product with administrator credentials."""
    create_response = client.post("/api/produits", json=PRODUCT_PAYLOAD, headers=admin_headers)

    assert create_response.status_code == 201
    created = create_response.get_json()
    assert isinstance(created, Mapping)
    product_id = created["id"]
    assert isinstance(product_id, int)
    product = db.session.get(Product, product_id)
    assert product is not None
    assert created == product.to_dict()

    replacement_payload = {
        **PRODUCT_PAYLOAD,
        "nom": "Silent Keyboard",
        "quantite_stock": 9,
    }
    update_response = client.put(
        f"/api/produits/{product_id}",
        json=replacement_payload,
        headers=admin_headers,
    )

    assert update_response.status_code == 200
    updated = db.session.get(Product, product_id)
    assert updated is not None
    assert update_response.get_json() == updated.to_dict()
    assert updated.nom == "Silent Keyboard"
    assert updated.quantite_stock == 9

    delete_response = client.delete(f"/api/produits/{product_id}", headers=admin_headers)

    assert delete_response.status_code == 200
    assert delete_response.get_json() == {"message": "Product deleted."}
    assert db.session.get(Product, product_id) is None


def test_update_product_rejects_incomplete_payload(
    client: FlaskClient, admin_headers: dict[str, str]
) -> None:
    """Reject an incomplete PUT without changing the persisted product."""
    create_response = client.post("/api/produits", json=PRODUCT_PAYLOAD, headers=admin_headers)
    created = create_response.get_json()
    assert create_response.status_code == 201
    assert isinstance(created, Mapping)
    product_id = created["id"]
    assert isinstance(product_id, int)

    incomplete_payload = {
        key: value for key, value in PRODUCT_PAYLOAD.items() if key != "categorie"
    }
    update_response = client.put(
        f"/api/produits/{product_id}",
        json=incomplete_payload,
        headers=admin_headers,
    )
    db.session.expire_all()
    persisted_product = db.session.get(Product, product_id)

    assert update_response.status_code == 400
    assert isinstance(update_response.get_json()["error"], str)
    assert persisted_product is not None
    assert persisted_product.to_dict() == created


def test_update_product_rejects_unknown_id(
    client: FlaskClient, admin_headers: dict[str, str]
) -> None:
    """Return the documented missing-product response for an unknown product."""
    update_response = client.put(
        "/api/produits/999",
        json=PRODUCT_PAYLOAD,
        headers=admin_headers,
    )

    assert update_response.status_code == 404
    assert update_response.get_json() == {"error": "Product not found."}
