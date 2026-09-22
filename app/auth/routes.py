"""HTTP routes for authentication."""

from typing import cast

from flask import Blueprint, Response, jsonify, request

from app.auth.service import (
    DuplicateEmailError,
    InvalidCredentialsError,
    ValidationError,
    login_user,
    register_user,
    validate_registration,
)

auth_blueprint = Blueprint("auth", __name__)


@auth_blueprint.post("/register")
def register() -> tuple[Response, int]:
    """Register a new client account from a JSON request.

    Returns:
        A `201` response containing public user fields, a `400` response for invalid input,
        or a `409` response when the normalized email is already registered.
    """
    # Treat decoded JSON as untrusted until the service validates that it is the expected object.
    payload = cast(object, request.get_json(silent=True))

    try:
        # Validation produces trusted registration data before database work begins.
        registration = validate_registration(payload)
        user = register_user(registration)
    except ValidationError as error:
        return jsonify({"error": str(error)}), 400
    except DuplicateEmailError as error:
        return jsonify({"error": str(error)}), 409

    return jsonify(user.to_dict()), 201


@auth_blueprint.post("/login")
def login() -> tuple[Response, int] | Response:
    """Authenticate JSON credentials and return a JWT access token.

    Returns:
        A `200` response containing an access token, a `400` response for invalid input,
        or a generic `401` response for invalid credentials.
    """
    # Treat decoded JSON as untrusted until login validation confirms its required fields.
    payload = cast(object, request.get_json(silent=True))

    try:
        # The service verifies credentials and creates a token without knowing HTTP details.
        token = login_user(payload)
    except ValidationError as error:
        return jsonify({"error": str(error)}), 400
    except InvalidCredentialsError as error:
        return jsonify({"error": str(error)}), 401

    return jsonify({"access_token": token})
