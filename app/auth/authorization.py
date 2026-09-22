"""JWT role authorization shared by protected feature routes."""

from collections.abc import Callable
from functools import wraps
from typing import ParamSpec, TypeAlias, cast

from flask import Response, jsonify
from flask_jwt_extended import get_jwt, jwt_required

from app.extensions import jwt

P = ParamSpec("P")
RouteResponse: TypeAlias = Response | tuple[Response, int]


def _unauthorized_response(message: str) -> tuple[Response, int]:
    """Return a JSON JWT authentication failure response."""
    return jsonify({"error": message}), 401


def register_jwt_error_handlers() -> None:
    """Register JSON error callbacks on the shared JWT extension."""

    @jwt.unauthorized_loader
    def handle_missing_token(reason: str) -> RouteResponse:
        """Return JSON for a request without a usable authorization header."""
        return _unauthorized_response(reason)

    @jwt.invalid_token_loader
    def handle_invalid_token(reason: str) -> RouteResponse:
        """Return JSON for an invalid JWT."""
        return _unauthorized_response(reason)

    @jwt.expired_token_loader
    def handle_expired_token(_: object, __: object) -> RouteResponse:
        """Return JSON for an expired JWT."""
        return _unauthorized_response("Token has expired.")


def admin_required(view: Callable[P, RouteResponse]) -> Callable[P, RouteResponse]:
    """Require an access token whose role claim grants administrator access."""
    require_jwt = cast(
        Callable[[Callable[P, RouteResponse]], Callable[P, RouteResponse]],
        jwt_required(),
    )

    @wraps(view)
    @require_jwt
    def wrapped(*args: P.args, **kwargs: P.kwargs) -> RouteResponse:
        """Authorize the request before invoking the protected view."""
        if get_jwt().get("role") != "admin":
            return jsonify({"error": "Administrator access is required."}), 403
        return view(*args, **kwargs)

    return wrapped
