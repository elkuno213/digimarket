"""Behavioral tests for order service rules."""

from datetime import UTC, datetime

import pytest
from flask import Flask

from app.extensions import db
from app.models.order import Order
from app.models.product import Product
from app.models.user import User
from app.orders.service import (
    InsufficientStockError,
    OrderAccessError,
    OrderedProductNotFoundError,
    OrderNotFoundError,
    OrderValidationError,
    StatusTransitionError,
    create_order,
    get_order,
    get_order_lines,
    list_orders,
    update_order_status,
    validate_order,
    validate_status,
)


def _product(name: str, price: float, stock: int) -> Product:
    """Persist a product with a distinct price and available stock."""
    product = Product(
        nom=name,
        description=name,
        categorie="Accessories",
        prix=price,
        quantite_stock=stock,
    )
    db.session.add(product)
    db.session.commit()
    return product


def test_create_order_snapshots_prices_without_reserving_stock(
    app: Flask, client_user: User
) -> None:
    """Capture current prices while leaving inventory available until validation."""
    keyboard = _product("Keyboard", 89.0, 5)
    mouse = _product("Mouse", 45.0, 8)

    # Validate the public payload before giving its normalized data to the service.
    data = validate_order(
        {
            "adresse_livraison": " 12 Rue Exemple, Paris ",
            "lignes": [
                {"produit_id": keyboard.id, "quantite": 2},
                {"produit_id": mouse.id, "quantite": 3},
            ],
        }
    )
    # Creating a pending order saves its lines but does not reserve inventory.
    order = create_order(data, client_user.id)
    lines = get_order_lines(order.id, client_user.id, "client")

    # Check saved values, including the price snapshot, rather than the original request.
    assert order.statut == "en_attente"
    assert order.adresse_livraison == "12 Rue Exemple, Paris"
    assert [(line.produit_id, line.quantite, line.prix_unitaire) for line in lines] == [
        (keyboard.id, 2, 89.0),
        (mouse.id, 3, 45.0),
    ]
    assert (keyboard.quantite_stock, mouse.quantite_stock) == (5, 8)


def test_validate_order_updates_all_stock_or_none(app: Flask, client_user: User) -> None:
    """A shortage in one line leaves every stock count and status intact."""
    keyboard = _product("Keyboard", 89.0, 5)
    mouse = _product("Mouse", 45.0, 5)
    # The first order can be supplied; the second cannot after the first is validated.
    first = create_order(
        validate_order(
            {
                "adresse_livraison": "Paris",
                "lignes": [
                    {"produit_id": keyboard.id, "quantite": 2},
                    {"produit_id": mouse.id, "quantite": 2},
                ],
            }
        ),
        client_user.id,
    )
    second = create_order(
        validate_order(
            {
                "adresse_livraison": "Lyon",
                "lignes": [
                    {"produit_id": keyboard.id, "quantite": 1},
                    {"produit_id": mouse.id, "quantite": 4},
                ],
            }
        ),
        client_user.id,
    )

    # A successful validation deducts each requested quantity and updates the status.
    update_order_status(first.id, "validée")
    assert (keyboard.quantite_stock, mouse.quantite_stock, first.statut) == (3, 3, "validée")

    # A later shortage must not leave a partial change in the session or database.
    with pytest.raises(InsufficientStockError):
        update_order_status(second.id, "validée")
    db.session.expire_all()
    assert (keyboard.quantite_stock, mouse.quantite_stock) == (3, 3)
    persisted_second = db.session.get(Order, second.id)
    assert persisted_second is not None
    assert persisted_second.statut == "en_attente"


def test_cancel_validated_order_restores_stock(app: Flask, client_user: User) -> None:
    """Cancellation returns the quantity deducted at validation."""
    keyboard = _product("Keyboard", 89.0, 5)
    order = create_order(
        validate_order(
            {
                "adresse_livraison": "Paris",
                "lignes": [{"produit_id": keyboard.id, "quantite": 2}],
            }
        ),
        client_user.id,
    )

    # Validation deducts stock; cancellation must restore the same quantity.
    update_order_status(order.id, "validée")
    assert keyboard.quantite_stock == 3
    update_order_status(order.id, "annulée")

    assert keyboard.quantite_stock == 5
    assert order.statut == "annulée"


def test_order_reads_require_owner_or_administrator(
    app: Flask, client_user: User, admin_user: User
) -> None:
    """Owners and admins can read an order; another client cannot."""
    keyboard = _product("Keyboard", 89.0, 5)
    other_client = User(
        email="other@example.com",
        password_hash="unused",
        nom="Other",
        role="client",
        date_creation=datetime.now(UTC),
    )
    # Persist a different client so ownership checks use a real actor identifier.
    db.session.add(other_client)
    db.session.commit()
    order = create_order(
        validate_order(
            {
                "adresse_livraison": "Paris",
                "lignes": [{"produit_id": keyboard.id, "quantite": 1}],
            }
        ),
        client_user.id,
    )

    # Owners and administrators can read, but listings remain scoped for ordinary clients.
    assert get_order(order.id, client_user.id, "client") == order
    assert get_order(order.id, admin_user.id, "admin") == order
    assert len(get_order_lines(order.id, admin_user.id, "admin")) == 1
    assert list_orders(client_user.id, "client") == [order]
    assert list_orders(admin_user.id, "admin") == [order]
    assert list_orders(other_client.id, "client") == []
    # The same ownership rule protects both an order header and its saved lines.
    with pytest.raises(OrderAccessError):
        get_order(order.id, other_client.id, "client")
    with pytest.raises(OrderAccessError):
        get_order_lines(order.id, other_client.id, "client")


@pytest.mark.parametrize(
    "payload",
    [
        {
            "adresse_livraison": "Paris",
            "lignes": [
                {"produit_id": 1, "quantite": 1},
                {"produit_id": 1, "quantite": 2},
            ],
        },
        {"adresse_livraison": "Paris", "lignes": [{"produit_id": 1, "quantite": 0}]},
        {"adresse_livraison": "Paris", "lignes": [{"produit_id": True, "quantite": 1}]},
        {"adresse_livraison": "  ", "lignes": [{"produit_id": 1, "quantite": 1}]},
        {"adresse_livraison": "Paris", "lignes": [{"produit_id": 1, "quantite": 2**63}]},
        {"adresse_livraison": "Paris", "lignes": [{"produit_id": 1}]},
    ],
)
def test_order_validation_rejects_duplicate_products_and_invalid_values(
    payload: dict[str, object],
) -> None:
    """Reject ambiguous lines and values that are invalid for persistence."""
    # Every parametrized payload must fail before an order can be created.
    with pytest.raises(OrderValidationError):
        validate_order(payload)


def test_final_order_status_rejects_new_transition(app: Flask, client_user: User) -> None:
    """Shipped orders cannot be cancelled or have stock restored."""
    keyboard = _product("Keyboard", 89.0, 5)
    order = create_order(
        validate_order(
            {
                "adresse_livraison": "Paris",
                "lignes": [{"produit_id": keyboard.id, "quantite": 1}],
            }
        ),
        client_user.id,
    )
    # Reach the terminal shipped state through the two allowed transitions.
    update_order_status(order.id, "validée")
    update_order_status(order.id, "expédiée")
    assert order.statut == "expédiée"

    # A shipped order cannot be cancelled, so its deducted stock stays deducted.
    with pytest.raises(StatusTransitionError):
        update_order_status(order.id, "annulée")
    assert keyboard.quantite_stock == 4


def test_status_payload_accepts_only_known_statuses() -> None:
    """Status input must contain exactly one recognized status."""
    # Accept one valid, exact-shape status payload.
    assert validate_status({"statut": "validée"}) == "validée"
    # Reject an extra field, an unknown value, and a value with the wrong type.
    with pytest.raises(OrderValidationError):
        validate_status({"statut": "validée", "extra": True})
    with pytest.raises(OrderValidationError):
        validate_status({"statut": "unknown"})
    with pytest.raises(OrderValidationError):
        validate_status({"statut": []})


def test_missing_product_and_order_raise_domain_errors(app: Flask, client_user: User) -> None:
    """Service callers receive domain errors for missing references."""
    # Creating an order with an unknown product fails before persistence.
    data = validate_order(
        {
            "adresse_livraison": "Paris",
            "lignes": [{"produit_id": 999, "quantite": 1}],
        }
    )
    with pytest.raises(OrderedProductNotFoundError):
        create_order(data, client_user.id)
    # Both order-reading functions use the same missing-order domain error.
    with pytest.raises(OrderNotFoundError):
        get_order(999, client_user.id, "client")
    with pytest.raises(OrderNotFoundError):
        get_order_lines(999, client_user.id, "client")
