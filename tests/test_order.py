"""Tests for persisted order models."""

from datetime import UTC, datetime

from flask import Flask

from app.extensions import db
from app.models.order import Order
from app.models.order_item import OrderItem
from app.models.product import Product
from app.models.user import User


def test_persisted_order_and_line_serialize_as_public_json(
    app: Flask, client_user: User, product: Product
) -> None:
    """Reload an order and line before checking their public fields."""
    order = Order(
        utilisateur_id=client_user.id,
        date_commande=datetime(2026, 9, 23, 9, 30, tzinfo=UTC),
        adresse_livraison="12 Rue Exemple, Paris",
        statut="en_attente",
    )
    line = OrderItem(
        commande=order,
        produit_id=product.id,
        quantite=2,
        prix_unitaire=49.99,
    )
    db.session.add_all([order, line])
    db.session.commit()
    order_id = order.id
    line_id = line.id
    user_id = client_user.id
    product_id = product.id
    db.session.remove()

    persisted_order = db.session.get(Order, order_id)
    persisted_line = db.session.get(OrderItem, line_id)

    assert persisted_order is not None
    assert persisted_line is not None
    assert persisted_order.to_dict() == {
        "id": order_id,
        "utilisateur_id": user_id,
        "date_commande": "2026-09-23T09:30:00+00:00",
        "adresse_livraison": "12 Rue Exemple, Paris",
        "statut": "en_attente",
    }
    assert persisted_line.to_dict() == {
        "id": line_id,
        "produit_id": product_id,
        "quantite": 2,
        "prix_unitaire": 49.99,
    }
