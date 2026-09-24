"""HTTP routes for public catalogue access and administrator product management."""

from typing import cast

from flask import Blueprint, Response, jsonify, request

from app.auth.authorization import admin_required
from app.products.service import (
    ProductNotFoundError,
    ProductReferencedByOrderError,
    ValidationError,
    create_product,
    delete_product,
    get_product,
    list_products,
    update_product,
    validate_product,
)

products_blueprint = Blueprint("products", __name__)


@products_blueprint.get("")
def list_products_route() -> Response:
    """Return the public catalogue without requiring authentication."""
    products = list_products(request.args.get("q"))
    return jsonify([product.to_dict() for product in products])


@products_blueprint.get("/<int:product_id>")
def get_product_route(product_id: int) -> tuple[Response, int] | Response:
    """Return one public product without requiring authentication."""
    try:
        product = get_product(product_id)
    except ProductNotFoundError as error:
        return jsonify({"error": str(error)}), 404

    return jsonify(product.to_dict())


@products_blueprint.post("")
@admin_required
def create_product_route() -> tuple[Response, int]:
    """Create a product from a complete administrator request."""
    payload = cast(object, request.get_json(silent=True))
    try:
        product_data = validate_product(payload)
    except ValidationError as error:
        return jsonify({"error": str(error)}), 400

    product = create_product(product_data)
    return jsonify(product.to_dict()), 201


@products_blueprint.put("/<int:product_id>")
@admin_required
def update_product_route(product_id: int) -> tuple[Response, int] | Response:
    """Fully replace one product from a complete administrator request."""
    payload = cast(object, request.get_json(silent=True))
    try:
        product_data = validate_product(payload)
        product = update_product(product_id, product_data)
    except ValidationError as error:
        return jsonify({"error": str(error)}), 400
    except ProductNotFoundError as error:
        return jsonify({"error": str(error)}), 404

    return jsonify(product.to_dict())


@products_blueprint.delete("/<int:product_id>")
@admin_required
def delete_product_route(product_id: int) -> tuple[Response, int] | Response:
    """Delete one product after administrator authentication."""
    try:
        delete_product(product_id)
    except ProductNotFoundError as error:
        return jsonify({"error": str(error)}), 404
    except ProductReferencedByOrderError as error:
        return jsonify({"error": str(error)}), 409

    return jsonify({"message": "Product deleted."})
