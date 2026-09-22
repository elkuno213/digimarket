"""HTTP routes for public product catalogue access."""

from flask import Blueprint, Response, jsonify, request

from app.products.service import ProductNotFoundError, get_product, list_products

products_blueprint = Blueprint("products", __name__)


@products_blueprint.get("")
def list_catalogue() -> Response:
    """Return the public catalogue, optionally filtered by text."""
    products = list_products(request.args.get("q"))
    return jsonify([product.to_dict() for product in products])


@products_blueprint.get("/<int:product_id>")
def get_product_detail(product_id: int) -> tuple[Response, int] | Response:
    """Return one public product or a missing-product error."""
    try:
        product = get_product(product_id)
    except ProductNotFoundError as error:
        return jsonify({"error": str(error)}), 404

    return jsonify(product.to_dict())
