"""Validation and persistence operations for products."""

from collections.abc import Mapping
from dataclasses import dataclass
from math import isfinite

from sqlalchemy import func, or_

from app.extensions import db
from app.models.order import Order
from app.models.order_item import OrderItem
from app.models.product import Product

_MIN_SQLITE_INTEGER = -(2**63)
_MAX_SQLITE_INTEGER = 2**63 - 1


class ValidationError(ValueError):
    """Raised when public product data is invalid."""


class ProductNotFoundError(LookupError):
    """Raised when a requested product does not exist."""


class ProductReferencedByOrderError(ValueError):
    """Raised when an order line prevents product deletion."""


@dataclass(frozen=True)
class ProductData:
    """Validated editable product values."""

    nom: str
    description: str
    categorie: str
    prix: float
    quantite_stock: int


def validate_product(payload: object) -> ProductData:
    """Validate a complete product create or replacement payload."""
    # Reject non-object JSON before reading named product fields.
    if not isinstance(payload, Mapping):
        raise ValidationError("Request body must be a JSON object.")

    # Normalize text and numeric values into the service's trusted data object.
    nom = _validated_text(payload.get("nom"), "nom")
    description = _validated_text(payload.get("description"), "description")
    categorie = _validated_text(payload.get("categorie"), "categorie")
    prix = _validated_price(payload.get("prix"))
    quantite_stock = _validated_stock(payload.get("quantite_stock"))

    return ProductData(
        nom=nom,
        description=description,
        categorie=categorie,
        prix=prix,
        quantite_stock=quantite_stock,
    )


def list_products(query: str | None) -> list[Product]:
    """Return products ordered by identifier, optionally filtered by text."""
    # Start from stable catalogue ordering, then add a literal Unicode-insensitive search.
    statement = db.select(Product).order_by(Product.id)
    search = query.strip().casefold() if query is not None else ""
    if search:
        # autoescape makes percent and underscore search characters literals.
        statement = statement.where(
            or_(
                func.unicode_casefold(Product.nom).contains(search, autoescape=True),
                func.unicode_casefold(Product.description).contains(search, autoescape=True),
                func.unicode_casefold(Product.categorie).contains(search, autoescape=True),
            )
        )
    return list(db.session.execute(statement).scalars())


def get_product(product_id: int) -> Product:
    """Return a product by identifier or raise the domain error."""
    # Reject values SQLite cannot represent before asking the database.
    if not _MIN_SQLITE_INTEGER <= product_id <= _MAX_SQLITE_INTEGER:
        raise ProductNotFoundError("Product not found.")
    product = db.session.get(Product, product_id)
    if product is None:
        raise ProductNotFoundError("Product not found.")
    return product


def create_product(data: ProductData) -> Product:
    """Persist a product from validated editable values."""
    # Construct the model only from trusted service data.
    product = Product(
        nom=data.nom,
        description=data.description,
        categorie=data.categorie,
        prix=data.prix,
        quantite_stock=_validated_stock(data.quantite_stock),
    )

    # Stage then commit the new catalogue record.
    db.session.add(product)
    _commit()

    return product


def update_product(product_id: int, data: ProductData) -> Product:
    """Replace a product's editable values with validated data."""
    # Load the existing record, then replace every editable field as PUT requires.
    product = get_product(product_id)

    product.nom = data.nom
    product.description = data.description
    product.categorie = data.categorie
    product.prix = data.prix
    product.quantite_stock = _validated_stock(data.quantite_stock)

    _commit()

    return product


def delete_product(product_id: int) -> None:
    """Delete a product and its pending orders unless protected history references it."""
    product = get_product(product_id)
    # Preserve every non-pending order and its lines as order history.
    referenced_id = db.session.scalar(
        db.select(OrderItem.id)
        .join(Order, OrderItem.commande_id == Order.id)
        .where(
            OrderItem.produit_id == product.id,
            or_(Order.statut != "en_attente", Order.statut.is_(None)),
        )
        .limit(1)
    )
    if referenced_id is not None:
        raise ProductReferencedByOrderError("Product is referenced by non-pending order history.")

    # Find pending orders containing this product; deleting one removes its complete order.
    pending_orders = db.session.scalars(
        db.select(Order)
        .join(OrderItem, OrderItem.commande_id == Order.id)
        .where(OrderItem.produit_id == product.id, Order.statut == "en_attente")
        .distinct()
    ).all()

    # TODO(elkuno213): Replace this destructive pending-order cleanup if a schema change becomes
    # allowed. A product lifecycle policy could remove a product from future catalogue and order
    # selection while retaining pending orders and all historical rows. Until then, hard deletion
    # must remove complete pending orders and their lines so the required order_item.produit_id
    # foreign key stays valid.
    # Delete lines before their order headers because this relationship has no delete cascade.
    for pending_order in pending_orders:
        for line in pending_order.lignes:
            db.session.delete(line)
        db.session.delete(pending_order)

    try:
        # Send line and order deletions first, before scheduling the product deletion.
        db.session.flush()
        db.session.delete(product)
    except Exception:
        # A failed flush leaves the session unusable until its transaction is rolled back.
        db.session.rollback()
        raise
    _commit()


def _validated_text(value: object, key: str) -> str:
    """Return a required nonblank text value."""
    if not isinstance(value, str):
        raise ValidationError(f"{key} must be a nonblank string.")
    stripped = value.strip()
    if not stripped:
        raise ValidationError(f"{key} must be a nonblank string.")
    return stripped


def _validated_price(value: object) -> float:
    """Return a finite, strictly positive product price."""
    # Reject booleans and non-numbers before converting supported JSON numbers.
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValidationError("prix must be a positive number.")
    try:
        prix = float(value)
    except OverflowError as error:
        raise ValidationError("prix must be a positive number.") from error
    if not isfinite(prix) or prix <= 0:
        raise ValidationError("prix must be a positive number.")
    return prix


def _validated_stock(value: object) -> int:
    """Return a stock value representable by SQLite's integer type."""
    # Keep JSON booleans, negative values, and SQLite-overflowing values out of persistence.
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or value < 0
        or value > _MAX_SQLITE_INTEGER
    ):
        raise ValidationError("quantite_stock must be a non-negative integer.")
    return value


def _commit() -> None:
    """Commit the active transaction and restore failed-session usability."""
    try:
        # Make all staged changes durable as one transaction.
        db.session.commit()
    except Exception:
        # Roll back so this scoped session can serve a later request.
        db.session.rollback()
        raise
