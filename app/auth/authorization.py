"""JWT role authorization shared by protected feature routes."""

from collections.abc import Callable
from functools import wraps
from typing import ParamSpec, TypeAlias

from flask import Response, abort, jsonify
from flask_jwt_extended import get_jwt, get_jwt_identity, verify_jwt_in_request

from app.extensions import jwt

P = ParamSpec("P")
RouteResponse: TypeAlias = Response | tuple[Response, int]


def _unauthorized_response(message: str) -> tuple[Response, int]:
    """Return a JSON JWT authentication failure response."""
    return jsonify({"error": message}), 401


def register_jwt_error_handlers() -> None:
    """Register JSON error callbacks on the shared JWT extension."""

    # Convert JWT extension failures into the API's common JSON error shape.
    @jwt.unauthorized_loader
    def on_missing_token(reason: str) -> RouteResponse:
        """Return JSON for a request without a usable authorization header."""
        return _unauthorized_response(reason)

    @jwt.invalid_token_loader
    def on_invalid_token(reason: str) -> RouteResponse:
        """Return JSON for an invalid JWT."""
        return _unauthorized_response(reason)

    @jwt.expired_token_loader
    def on_expired_token(_: object, __: object) -> RouteResponse:
        """Return JSON for an expired JWT."""
        return _unauthorized_response("Token has expired.")


def get_current_actor() -> tuple[int, str]:
    """Read the actor from an already verified access token."""
    # Read and validate the claims before application services use them for access checks.
    id = get_jwt_identity()
    role = get_jwt().get("role")
    if not isinstance(id, str) or not id.isdecimal() or not isinstance(role, str):
        abort(401, description="Token identity is invalid.")
    return int(id), role


def admin_required(view: Callable[P, RouteResponse]) -> Callable[P, RouteResponse]:
    """Require an access token whose role claim grants administrator access."""

    @wraps(view)
    def wrapped(*args: P.args, **kwargs: P.kwargs) -> RouteResponse:
        """Authorize the request before invoking the protected view."""
        # Verify signature and expiry first, then enforce the role claim.
        verify_jwt_in_request()
        _, role = get_current_actor()
        if role != "admin":
            return jsonify({"error": "Administrator access is required."}), 403
        return view(*args, **kwargs)

    return wrapped
