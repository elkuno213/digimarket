"""Tests for authenticated order routes."""

from collections.abc import Mapping
from datetime import UTC, datetime

import pytest
from flask import Flask
from flask.testing import FlaskClient
from flask_jwt_extended import create_access_token
from werkzeug.security import generate_password_hash

from app.extensions import db
from app.models.product import Product
from app.models.user import User


@pytest.fixture
def other_client(app: Flask) -> tuple[User, dict[str, str]]:
    """Provide another persisted client and an access token."""
    # Persist a separate account so ownership checks cannot accidentally use the fixture user.
    user = User(
        email="other-client@example.com",
        password_hash=generate_password_hash("correct-password"),
        nom="Other Client",
        role="client",
        date_creation=datetime.now(UTC),
    )
    db.session.add(user)
    db.session.commit()
    # Build the same identity and role claims that the login service places in an access token.
    token = create_access_token(identity=str(user.id), additional_claims={"role": user.role})
    return user, {"Authorization": f"Bearer {token}"}


def test_client_can_create_and_read_own_order(
    client: FlaskClient,
    client_headers: dict[str, str],
    client_user: User,
    product: Product,
) -> None:
    """Create an order and read its header and saved line as the owner."""
    order_payload = {
        "adresse_livraison": "  10 Main Street  ",
        "lignes": [{"produit_id": product.id, "quantite": 2}],
    }

    # Whitespace in the address proves that the public API normalizes validated text.
    created = client.post("/api/commandes", json=order_payload, headers=client_headers)

    # Verify the creation response is an order header, not a response containing its lines.
    assert created.status_code == 201
    order = created.get_json()
    assert isinstance(order, Mapping)
    assert set(order) == {
        "id",
        "utilisateur_id",
        "date_commande",
        "adresse_livraison",
        "statut",
    }
    assert order["utilisateur_id"] == client_user.id
    assert order["adresse_livraison"] == "10 Main Street"
    assert order["statut"] == "en_attente"
    assert isinstance(order["date_commande"], str)

    # Change the catalogue price after creation; saved lines must retain their original price.
    original_price = product.prix
    product.prix = 29.99
    db.session.commit()
    order_id = order["id"]
    listed = client.get("/api/commandes", headers=client_headers)
    detail = client.get(f"/api/commandes/{order_id}", headers=client_headers)
    lines = client.get(f"/api/commandes/{order_id}/lignes", headers=client_headers)

    # The owner can use all three read endpoints and sees the saved price snapshot.
    assert listed.status_code == detail.status_code == lines.status_code == 200
    assert listed.get_json() == [order]
    assert detail.get_json() == order
    assert lines.get_json() == [
        {
            "id": 1,
            "produit_id": product.id,
            "quantite": 2,
            "prix_unitaire": original_price,
        }
    ]


def test_order_visibility_and_administrator_update(
    client: FlaskClient,
    client_headers: dict[str, str],
    admin_headers: dict[str, str],
    other_client: tuple[User, dict[str, str]],
    product: Product,
) -> None:
    """Deny another client while allowing an admin to list and validate orders."""
    payload = {
        "adresse_livraison": "10 Main Street",
        "lignes": [{"produit_id": product.id, "quantite": 1}],
    }
    # Create one order per client so an administrator has two records to list.
    first = client.post("/api/commandes", json=payload, headers=client_headers)
    _, other_headers = other_client
    second = client.post("/api/commandes", json=payload, headers=other_headers)
    assert first.status_code == second.status_code == 201
    first_order = first.get_json()
    second_order = second.get_json()
    order_id = first_order["id"]

    # A client cannot inspect another client's order header or its item lines.
    detail = client.get(f"/api/commandes/{order_id}", headers=other_headers)
    lines = client.get(f"/api/commandes/{order_id}/lignes", headers=other_headers)

    assert detail.status_code == lines.status_code == 403
    assert detail.get_json() == lines.get_json() == {"error": "Order access denied."}

    # An administrator sees both orders and can validate either one.
    listed = client.get("/api/commandes", headers=admin_headers)
    updated = client.patch(
        f"/api/commandes/{order_id}",
        json={"statut": "validée"},
        headers=admin_headers,
    )

    assert listed.status_code == 200
    assert listed.get_json() == [first_order, second_order]
    assert updated.status_code == 200
    assert updated.get_json() == {**first_order, "statut": "validée"}
    # Validating through the route delegates to the stock-deduction service rule.
    db.session.refresh(product)
    assert product.quantite_stock == 4


def test_order_routes_require_authentication_and_admin_status_access(
    client: FlaskClient,
    client_headers: dict[str, str],
    product: Product,
) -> None:
    """Require a valid actor on every route and an administrator for status changes."""
    payload = {
        "adresse_livraison": "10 Main Street",
        "lignes": [{"produit_id": product.id, "quantite": 1}],
    }
    # Create an order first because detail, lines, and status routes need an existing ID.
    created = client.post("/api/commandes", json=payload, headers=client_headers)
    assert created.status_code == 201
    order_id = created.get_json()["id"]
    # Each protected endpoint must reject a request with no access token.
    requests = [
        client.get("/api/commandes"),
        client.get(f"/api/commandes/{order_id}"),
        client.get(f"/api/commandes/{order_id}/lignes"),
        client.post("/api/commandes", json=payload),
        client.patch(f"/api/commandes/{order_id}", json={"statut": "validée"}),
    ]

    assert all(response.status_code == 401 for response in requests)
    assert all(isinstance(response.get_json()["error"], str) for response in requests)
    # A valid client token still lacks the administrator role needed to change a status.
    denied = client.patch(
        f"/api/commandes/{order_id}",
        json={"statut": "validée"},
        headers=client_headers,
    )
    assert denied.status_code == 403
    assert denied.get_json() == {"error": "Administrator access is required."}

    # Signed tokens with malformed identity or role claims are also rejected.
    for identity, role in (("not-a-number", "client"), ("1", 42)):
        token = create_access_token(identity=identity, additional_claims={"role": role})
        invalid_actor = client.get(
            "/api/commandes",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert invalid_actor.status_code == 401
        assert invalid_actor.get_json() == {"error": "Token identity is invalid."}


def test_order_routes_map_validation_missing_and_stock_errors(
    client: FlaskClient,
    client_headers: dict[str, str],
    product: Product,
) -> None:
    """Map representative validation, lookup, and stock failures to public statuses."""
    # Exercise one request for each public error family: validation, missing resource, and conflict.
    responses = (
        (client.post("/api/commandes", json={}, headers=client_headers), 400),
        (client.get("/api/commandes/999", headers=client_headers), 404),
        (
            client.post(
                "/api/commandes",
                json={
                    "adresse_livraison": "10 Main Street",
                    "lignes": [{"produit_id": product.id, "quantite": 6}],
                },
                headers=client_headers,
            ),
            409,
        ),
    )

    for response, status in responses:
        assert response.status_code == status
        assert isinstance(response.get_json()["error"], str)
