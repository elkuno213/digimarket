"""Tests for public product catalogue routes."""

from collections.abc import Mapping
from datetime import timedelta

import pytest
from flask import Flask
from flask.testing import FlaskClient
from flask_jwt_extended import create_access_token
from sqlalchemy.exc import SQLAlchemyError

from app.extensions import db
from app.models.product import Product
from app.models.user import User

PRODUCT_PAYLOAD: dict[str, object] = {
    "nom": "Keyboard",
    "description": "Quiet switches",
    "categorie": "Accessories",
    "prix": 89.99,
    "quantite_stock": 4,
}


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


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("POST", "/api/produits"),
        ("PUT", "/api/produits/999"),
        ("DELETE", "/api/produits/999"),
    ],
    ids=["create", "replace", "delete"],
)
def test_product_writes_require_administrator(
    app: Flask,
    client: FlaskClient,
    client_headers: dict[str, str],
    admin_user: User,
    method: str,
    path: str,
) -> None:
    """Reject invalid and non-administrator credentials for every product write."""
    with app.app_context():
        expired_token = create_access_token(
            identity=str(admin_user.id),
            additional_claims={"role": admin_user.role},
            expires_delta=timedelta(seconds=-1),
        )

    missing_token_response = client.open(path, method=method, json=PRODUCT_PAYLOAD)
    malformed_token_response = client.open(
        path,
        method=method,
        json=PRODUCT_PAYLOAD,
        headers={"Authorization": "Bearer not-a-token"},
    )
    client_response = client.open(
        path,
        method=method,
        json=PRODUCT_PAYLOAD,
        headers=client_headers,
    )
    expired_token_response = client.open(
        path,
        method=method,
        json=PRODUCT_PAYLOAD,
        headers={"Authorization": f"Bearer {expired_token}"},
    )

    assert missing_token_response.status_code == 401
    assert isinstance(missing_token_response.get_json()["error"], str)
    assert malformed_token_response.status_code == 401
    assert isinstance(malformed_token_response.get_json()["error"], str)
    assert client_response.status_code == 403
    assert client_response.get_json() == {"error": "Administrator access is required."}
    assert expired_token_response.status_code == 401
    assert expired_token_response.get_json() == {"error": "Token has expired."}


@pytest.mark.parametrize(
    "payload",
    [
        {**PRODUCT_PAYLOAD, "nom": " "},
        {**PRODUCT_PAYLOAD, "prix": 0},
        {**PRODUCT_PAYLOAD, "quantite_stock": -1},
        {**PRODUCT_PAYLOAD, "quantite_stock": True},
    ],
    ids=["blank_name", "zero_price", "negative_stock", "boolean_stock"],
)
def test_admin_create_rejects_invalid_product_payloads(
    client: FlaskClient, admin_headers: dict[str, str], payload: object
) -> None:
    """Reject representative invalid full product payloads before persistence."""
    response = client.post("/api/produits", json=payload, headers=admin_headers)

    assert response.status_code == 400
    assert isinstance(response.get_json()["error"], str)
    assert db.session.scalar(db.select(Product)) is None


def test_administrator_can_create_replace_and_delete_product(
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


def test_administrator_cannot_partially_replace_an_existing_product(
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


def test_administrator_writes_report_unknown_product_ids(
    client: FlaskClient, admin_headers: dict[str, str]
) -> None:
    """Return the documented missing-product response for replacement and deletion."""
    update_response = client.put(
        "/api/produits/999",
        json=PRODUCT_PAYLOAD,
        headers=admin_headers,
    )
    delete_response = client.delete("/api/produits/999", headers=admin_headers)

    assert update_response.status_code == 404
    assert update_response.get_json() == {"error": "Product not found."}
    assert delete_response.status_code == 404
    assert delete_response.get_json() == {"error": "Product not found."}


def test_product_creation_recovers_after_a_commit_failure(
    client: FlaskClient, admin_headers: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Return a non-leaking server error and restore product creation after a failed commit."""

    def fail_commit() -> None:
        raise SQLAlchemyError("simulated write failure")

    with monkeypatch.context() as patch:
        patch.setattr(db.session, "commit", fail_commit)
        failed_response = client.post("/api/produits", json=PRODUCT_PAYLOAD, headers=admin_headers)

    assert failed_response.status_code == 500
    assert failed_response.get_json() == {"error": "Internal server error."}
    assert db.session.scalar(db.select(Product)) is None

    recovered_response = client.post("/api/produits", json=PRODUCT_PAYLOAD, headers=admin_headers)

    assert recovered_response.status_code == 201
    assert len(list(db.session.scalars(db.select(Product)))) == 1
