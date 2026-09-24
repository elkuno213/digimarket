"""HTTP routes for authenticated orders."""

from typing import cast

from flask import Blueprint, Response, jsonify, request
from flask_jwt_extended import verify_jwt_in_request

from app.auth.authorization import admin_required, get_current_actor
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

orders_blueprint = Blueprint("orders", __name__)


@orders_blueprint.errorhandler(OrderAccessError)
def on_order_access_error(error: OrderAccessError) -> tuple[Response, int]:
    """Return a JSON ownership denial."""
    return jsonify({"error": str(error)}), 403


@orders_blueprint.errorhandler(OrderValidationError)
@orders_blueprint.errorhandler(OrderNotFoundError)
@orders_blueprint.errorhandler(OrderedProductNotFoundError)
@orders_blueprint.errorhandler(InsufficientStockError)
@orders_blueprint.errorhandler(StatusTransitionError)
def on_order_service_error(
    error: OrderValidationError
    | OrderNotFoundError
    | OrderedProductNotFoundError
    | InsufficientStockError
    | StatusTransitionError,
) -> tuple[Response, int]:
    """Map order service failures to JSON HTTP errors."""
    if isinstance(error, OrderValidationError):
        status = 400
    elif isinstance(error, OrderNotFoundError | OrderedProductNotFoundError):
        status = 404
    else:
        status = 409
    return jsonify({"error": str(error)}), status


@orders_blueprint.get("")
def list_orders_route() -> Response:
    """List orders visible to the authenticated actor."""
    verify_jwt_in_request()
    actor_id, role = get_current_actor()
    return jsonify([order.to_dict() for order in list_orders(actor_id, role)])


@orders_blueprint.get("/<int:order_id>")
def get_order_route(order_id: int) -> Response:
    """Return one order visible to the authenticated actor."""
    verify_jwt_in_request()
    actor_id, role = get_current_actor()
    return jsonify(get_order(order_id, actor_id, role).to_dict())


@orders_blueprint.post("")
def create_order_route() -> tuple[Response, int]:
    """Create a pending order for the authenticated actor."""
    verify_jwt_in_request()
    actor_id, _ = get_current_actor()
    payload = cast(object, request.get_json(silent=True))
    return jsonify(create_order(validate_order(payload), actor_id).to_dict()), 201


@orders_blueprint.patch("/<int:order_id>")
@admin_required
def update_order_status_route(order_id: int) -> Response:
    """Apply an administrator's requested status transition."""
    payload = cast(object, request.get_json(silent=True))
    return jsonify(update_order_status(order_id, validate_status(payload)).to_dict())


@orders_blueprint.get("/<int:order_id>/lignes")
def get_order_lines_route(order_id: int) -> Response:
    """Return saved lines for one visible order."""
    verify_jwt_in_request()
    actor_id, role = get_current_actor()
    return jsonify([line.to_dict() for line in get_order_lines(order_id, actor_id, role)])
