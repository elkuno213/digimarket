"""Tests for public product catalogue routes."""

from collections.abc import Mapping
from datetime import UTC, datetime

import pytest
from flask.testing import FlaskClient
from sqlalchemy import text

from app.extensions import db
from app.models.order import Order
from app.models.order_item import OrderItem
from app.models.product import Product
from app.models.user import User

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


def _create_order(user: User, status: str | None, products: list[Product]) -> Order:
    """Persist an order with one line per supplied product."""
    order = Order(
        utilisateur_id=user.id,
        date_commande=datetime.now(UTC),
        adresse_livraison="10 Main Street",
        statut=status,
    )
    db.session.add(order)
    db.session.flush()
    db.session.add_all(
        OrderItem(
            commande_id=order.id,
            produit_id=ordered_product.id,
            quantite=1,
            prix_unitaire=ordered_product.prix,
        )
        for ordered_product in products
    )
    db.session.commit()
    return order


def test_delete_product_removes_complete_pending_order(
    client: FlaskClient,
    admin_headers: dict[str, str],
    client_user: User,
    product: Product,
) -> None:
    """Delete every pending order line while keeping the other product and its stock."""
    other_product = Product(
        nom="Mouse",
        description="Ergonomic mouse",
        categorie="Accessories",
        prix=49.99,
        quantite_stock=7,
    )
    db.session.add(other_product)
    db.session.commit()
    order = _create_order(client_user, "en_attente", [product, other_product])
    order_id = order.id
    line_ids = [line.id for line in order.lignes]
    product_id = product.id
    other_product_id = other_product.id
    other_stock = other_product.quantite_stock

    response = client.delete(f"/api/produits/{product_id}", headers=admin_headers)
    db.session.expire_all()

    assert response.status_code == 200
    assert response.get_json() == {"message": "Product deleted."}
    assert db.session.get(Product, product_id) is None
    assert db.session.get(Order, order_id) is None
    assert all(db.session.get(OrderItem, line_id) is None for line_id in line_ids)
    remaining_product = db.session.get(Product, other_product_id)
    assert remaining_product is not None
    assert remaining_product.quantite_stock == other_stock


def test_delete_product_with_foreign_keys_enabled(
    client: FlaskClient,
    admin_headers: dict[str, str],
    client_user: User,
    product: Product,
) -> None:
    """Remove pending lines before their product when SQLite enforces foreign keys."""
    order = _create_order(client_user, "en_attente", [product])
    product_id = product.id
    order_id = order.id
    line_id = order.lignes[0].id
    db.session.remove()
    db.session.execute(text("PRAGMA foreign_keys = ON"))
    assert db.session.scalar(text("PRAGMA foreign_keys")) == 1
    db.session.remove()

    response = client.delete(f"/api/produits/{product_id}", headers=admin_headers)
    db.session.expire_all()

    assert response.status_code == 200
    assert db.session.get(Product, product_id) is None
    assert db.session.get(Order, order_id) is None
    assert db.session.get(OrderItem, line_id) is None


@pytest.mark.parametrize("status", ["validée", "expédiée", "annulée", None, "other"])
def test_delete_product_preserves_non_pending_history_and_pending_orders(
    client: FlaskClient,
    admin_headers: dict[str, str],
    client_user: User,
    product: Product,
    status: str | None,
) -> None:
    """Reject deletion without changing protected or pending orders and their lines."""
    protected_order = _create_order(client_user, status, [product])
    pending_order = _create_order(client_user, "en_attente", [product])
    product_id = product.id
    product_snapshot = product.to_dict()
    order_ids = [protected_order.id, pending_order.id]
    line_ids = [protected_order.lignes[0].id, pending_order.lignes[0].id]
    order_snapshots = [protected_order.to_dict(), pending_order.to_dict()]
    line_snapshots = [protected_order.lignes[0].to_dict(), pending_order.lignes[0].to_dict()]

    response = client.delete(f"/api/produits/{product_id}", headers=admin_headers)
    db.session.expire_all()

    assert response.status_code == 409
    assert isinstance(response.get_json()["error"], str)
    remaining_product = db.session.get(Product, product_id)
    assert remaining_product is not None
    assert remaining_product.to_dict() == product_snapshot
    remaining_orders = [db.session.get(Order, order_id) for order_id in order_ids]
    remaining_lines = [db.session.get(OrderItem, line_id) for line_id in line_ids]
    assert [order.to_dict() for order in remaining_orders if order is not None] == order_snapshots
    assert [line.to_dict() for line in remaining_lines if line is not None] == line_snapshots


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
