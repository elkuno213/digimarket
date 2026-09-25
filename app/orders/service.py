"""Validation and persistence operations for orders."""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime

from app.extensions import db
from app.models.order import Order
from app.models.order_item import OrderItem
from app.models.product import Product

_MIN_SQLITE_INTEGER = -(2**63)
_MAX_SQLITE_INTEGER = 2**63 - 1


class OrderValidationError(ValueError):
    """Raised when an order payload is invalid."""


class OrderNotFoundError(LookupError):
    """Raised when an order does not exist."""


class OrderAccessError(PermissionError):
    """Raised when a caller cannot read an order."""


class OrderedProductNotFoundError(LookupError):
    """Raised when an ordered product does not exist."""


class InsufficientStockError(ValueError):
    """Raised when an order line cannot be supplied."""


class StatusTransitionError(ValueError):
    """Raised when an order status change is forbidden."""


@dataclass(frozen=True)
class OrderLineData:
    """Validated product and quantity for an order line."""

    produit_id: int
    quantite: int


@dataclass(frozen=True)
class OrderData:
    """Validated delivery address and order lines."""

    adresse_livraison: str
    lignes: tuple[OrderLineData, ...]


def validate_order(payload: object) -> OrderData:
    """Validate an order creation payload and trim its address."""
    if not isinstance(payload, Mapping) or payload.keys() != {"adresse_livraison", "lignes"}:
        raise OrderValidationError("Order must be a JSON object.")

    # Validate and normalize the address after confirming the request has both required keys.
    address = payload["adresse_livraison"]
    if not isinstance(address, str) or not address.strip():
        raise OrderValidationError("adresse_livraison must be nonblank text.")

    # Require a nonempty JSON array before validating each requested order line.
    raw_lines = payload["lignes"]
    if not isinstance(raw_lines, list) or not raw_lines:
        raise OrderValidationError("lignes must be a nonempty list.")

    # Build safe order-line data while remembering product IDs already requested.
    lines = []
    seen_products = set()
    for line in raw_lines:
        if not isinstance(line, Mapping) or line.keys() != {"produit_id", "quantite"}:
            raise OrderValidationError("Each line must contain a product and quantity.")

        # Read values only after confirming that each line has exactly the expected fields.
        product_id = line["produit_id"]
        quantity = line["quantite"]
        for value in (product_id, quantity):
            if type(value) is not int or not 0 < value <= _MAX_SQLITE_INTEGER:
                raise OrderValidationError("Line values must be positive SQLite integers.")

        # Reject duplicate products so each product has one requested quantity per order.
        if product_id in seen_products:
            raise OrderValidationError("Each product may appear only once.")
        seen_products.add(product_id)
        lines.append(OrderLineData(produit_id=product_id, quantite=quantity))

    return OrderData(adresse_livraison=address.strip(), lignes=tuple(lines))


def validate_status(payload: object) -> str:
    """Validate an order status payload."""
    # Require exactly one known status field before any state transition is considered.
    if not isinstance(payload, Mapping) or payload.keys() != {"statut"}:
        raise OrderValidationError("Status must be a JSON object with statut.")
    status = payload["statut"]
    if not isinstance(status, str) or status not in {
        "en_attente",
        "validée",
        "expédiée",
        "annulée",
    }:
        raise OrderValidationError("Unknown order status.")
    return status


def create_order(data: OrderData, utilisateur_id: int) -> Order:
    """Persist a pending order with current product price snapshots."""
    # Load every referenced product once and index the results for the following validations.
    products = {
        product.id: product
        for product in db.session.execute(
            db.select(Product).where(Product.id.in_(line.produit_id for line in data.lignes))
        ).scalars()
    }
    # Fail before writing when a requested product no longer exists in the catalogue.
    for line in data.lignes:
        if line.produit_id not in products:
            raise OrderedProductNotFoundError("Ordered product not found.")
    # Confirm that every requested quantity is available; pending orders do not change stock.
    for line in data.lignes:
        product = products[line.produit_id]
        if product.quantite_stock is None or product.quantite_stock < line.quantite:
            raise InsufficientStockError("Insufficient stock for ordered product.")
    # Create the pending order header before attaching its validated item lines.
    order = Order(
        utilisateur_id=utilisateur_id,
        date_commande=datetime.now(UTC),
        adresse_livraison=data.adresse_livraison,
        statut="en_attente",
    )
    # Snapshot prices now; inventory changes only when the order is validated.
    order.lignes = [
        OrderItem(
            produit_id=line.produit_id,
            quantite=line.quantite,
            prix_unitaire=products[line.produit_id].prix,
        )
        for line in data.lignes
    ]
    db.session.add(order)
    _commit()
    return order


def get_order_lines(order_id: int, utilisateur_id: int, role: str) -> list[OrderItem]:
    """Return lines for an order visible to the caller."""
    # Check header visibility first; only then query its saved line records.
    get_order(order_id, utilisateur_id, role)
    return list(
        db.session.execute(
            db.select(OrderItem).where(OrderItem.commande_id == order_id).order_by(OrderItem.id)
        ).scalars()
    )


def get_order(order_id: int, utilisateur_id: int, role: str) -> Order:
    """Return an order visible to the caller only if the caller is an admin or owns the order."""
    # Load once, then allow administrators or the order owner.
    order = _load_order(order_id)
    if role != "admin" and order.utilisateur_id != utilisateur_id:
        raise OrderAccessError("Order access denied.")
    return order


def list_orders(utilisateur_id: int, role: str) -> list[Order]:
    """Return orders visible to the caller only if the caller is an admin or owns the orders."""
    # Administrators see every header; clients receive only their own records.
    statement = db.select(Order).order_by(Order.id)
    if role != "admin":
        statement = statement.where(Order.utilisateur_id == utilisateur_id)
    return list(db.session.execute(statement).scalars())


def update_order_status(order_id: int, statut: str) -> Order:
    """Apply one permitted order status transition.

    Allowed transitions:

        Current state   Requested state   Stock effect
        en_attente      validée           Deduct ordered quantities.
        en_attente      annulée           Leave stock unchanged.
        validée         expédiée          Leave stock unchanged.
        validée         annulée           Restore ordered quantities.

    No other transition is allowed.

    Raises:
        InsufficientStockError: If stock is unavailable or cannot be safely restored.
        StatusTransitionError: If the current and requested states are not an allowed transition.
    """
    # Load current state once, then choose one allowed transition path.
    order = _load_order(order_id)
    # Validate only after every order line can be supplied.
    if order.statut == "en_attente" and statut == "validée":
        lines, products = _lines_and_products(order_id)
        # Plan all deductions before mutating stock.
        decremented_stocks = []
        for line in lines:
            product = products.get(line.produit_id)
            if (
                product is None
                or product.quantite_stock is None
                or product.quantite_stock < line.quantite
            ):
                raise InsufficientStockError("Insufficient stock for ordered product.")
            decremented_stocks.append((product, product.quantite_stock - line.quantite))
        for product, decremented_stock in decremented_stocks:
            product.quantite_stock = decremented_stock
        order.statut = statut
    # Cancelling a validated order restores its deducted stock.
    elif order.statut == "validée" and statut == "annulée":
        lines, products = _lines_and_products(order_id)
        # Plan all restorations before mutating stock.
        restored_stocks = []
        for line in lines:
            product = products.get(line.produit_id)
            if product is None or product.quantite_stock is None:
                raise InsufficientStockError("Ordered product stock is unavailable.")
            if product.quantite_stock > _MAX_SQLITE_INTEGER - line.quantite:
                raise InsufficientStockError(
                    "Restoring ordered product stock exceeds SQLite limit."
                )
            restored_stocks.append((product, product.quantite_stock + line.quantite))
        for product, restored_stock in restored_stocks:
            product.quantite_stock = restored_stock
        order.statut = statut
    # These transitions change only the status.
    elif (order.statut, statut) in {
        ("en_attente", "annulée"),
        ("validée", "expédiée"),
    }:
        order.statut = statut
    # Reject all other transitions.
    else:
        raise StatusTransitionError("Order status transition is not allowed.")
    _commit()
    return order


def _load_order(order_id: int) -> Order:
    """Return an order whose identifier fits SQLite's signed integer range."""
    # Reject non-representable identifiers before the database lookup.
    if not _MIN_SQLITE_INTEGER <= order_id <= _MAX_SQLITE_INTEGER:
        raise OrderNotFoundError("Order not found.")
    order = db.session.get(Order, order_id)
    if order is None:
        raise OrderNotFoundError("Order not found.")
    return order


def _lines_and_products(order_id: int) -> tuple[list[OrderItem], dict[int, Product]]:
    """Load order lines and their products in two queries."""
    # Load lines first, then index only their referenced products for stock operations.
    lines = list(
        db.session.execute(db.select(OrderItem).where(OrderItem.commande_id == order_id)).scalars()
    )
    products = {
        product.id: product
        for product in db.session.execute(
            db.select(Product).where(Product.id.in_(line.produit_id for line in lines))
        ).scalars()
    }
    return lines, products


def _commit() -> None:
    """Commit changes and restore the session after failure."""
    try:
        # Make staged order and stock changes durable as one transaction.
        db.session.commit()
    except Exception:
        # Roll back the failed transaction before the session is reused.
        db.session.rollback()
        raise
