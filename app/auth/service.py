"""Business logic for account registration and login."""

import re
from collections.abc import Mapping
from dataclasses import dataclass

from flask_jwt_extended import create_access_token
from sqlalchemy.exc import IntegrityError
from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import db
from app.models.user import User

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
DUMMY_PASSWORD_HASH = (
    "scrypt:32768:8:1$Tgf2dJoVPPUweXCo$3c4126c9077d9d7fccd3eda9653a49c2dcaaeb33847743137"
    "1159bd80beb8476c20bd021ebb6b3e56c144e370d803f6a0f11cf21fd2f7041b08c814226a6e70a"
)


class ValidationError(ValueError):
    """Raised when authentication request input does not satisfy the public contract."""


class DuplicateEmailError(ValueError):
    """Raised when a client email is already registered."""


class InvalidCredentialsError(ValueError):
    """Raised when login credentials cannot authenticate a user."""


@dataclass(frozen=True)
class RegistrationData:
    """Validated values needed to create a client account."""

    email: str
    name: str
    password: str


@dataclass(frozen=True)
class LoginData:
    """Validated credentials needed to authenticate a user."""

    email: str
    password: str


def require_json(payload: object) -> Mapping[object, object]:
    """Return a decoded JSON object or raise a validation error."""
    if not isinstance(payload, Mapping):
        raise ValidationError("Request body must be a JSON object.")
    return payload


def require_str(payload: Mapping[object, object], key: str) -> str:
    """Return a required nonblank text field from a decoded JSON object."""
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"{key} must be a nonblank string.")
    return value


def find_user_by_email(email: str) -> User | None:
    """Find a user by normalized email.

    Args:
        email: The normalized email address to look up.

    Returns:
        The matching user, if one exists.
    """
    statement = db.select(User).where(User.email == email)
    return db.session.scalars(statement).one_or_none()


def validate_registration(payload: object) -> RegistrationData:
    """Validate and normalize a registration JSON payload.

    Args:
        payload: The decoded JSON value from the HTTP request.

    Returns:
        The validated registration data.

    Raises:
        ValidationError: If the payload is not a valid registration object.
    """
    payload_json = require_json(payload=payload)
    email = require_str(payload_json, "email").strip().lower()  # email must be lowercase
    name = require_str(payload=payload_json, key="nom").strip()
    password = require_str(payload=payload_json, key="mot_de_passe")

    if EMAIL_PATTERN.fullmatch(email) is None:
        raise ValidationError("Email address is invalid.")
    if len(password) < 8:
        raise ValidationError("Password must contain at least 8 characters.")

    return RegistrationData(email=email, name=name, password=password)


def register_user(registration: RegistrationData) -> User:
    """Persist a new client account.

    Args:
        registration: Validated values for the new account.

    Returns:
        The persisted client user.

    Raises:
        DuplicateEmailError: If the normalized email is already registered.
    """
    # Give the usual duplicate case a clear application-level error before hashing.
    if find_user_by_email(registration.email) is not None:
        raise DuplicateEmailError("An account already exists for this email.")

    # The raw password stays outside the model and is hashed before User construction.
    password_hash = generate_password_hash(registration.password)

    # add() stages the insert; commit() below makes the transaction permanent.
    user = User(
        email=registration.email,
        password_hash=password_hash,
        nom=registration.name,
        role="client",  # Public registration must never grant administrator access.
    )
    db.session.add(user)

    try:
        db.session.commit()
    except IntegrityError:
        # The database unique constraint catches requests that passed the same pre-check together.
        # A rollback resets this failed session before we return the public duplicate-email error.
        db.session.rollback()
        raise DuplicateEmailError("An account already exists for this email.") from None

    return user


def validate_login(payload: object) -> LoginData:
    """Validate and normalize a login JSON payload.

    Args:
        payload: The decoded JSON value from the HTTP request.

    Returns:
        The validated login credentials.

    Raises:
        ValidationError: If the payload is not a valid login object.
    """
    payload_json = require_json(payload=payload)
    email = require_str(payload_json, "email").strip().lower()
    password = require_str(payload=payload_json, key="mot_de_passe")

    if EMAIL_PATTERN.fullmatch(email) is None:
        raise ValidationError("Email address is invalid.")

    return LoginData(email=email, password=password)


def login_user(payload: object) -> str:
    """Authenticate login input and return an access token.

    Args:
        payload: The decoded JSON value from the HTTP request.

    Returns:
        A signed access token for the authenticated user.

    Raises:
        InvalidCredentialsError: If the credentials do not authenticate a user.
        ValidationError: If the payload is not a valid login object.
    """
    login = validate_login(payload=payload)
    user = find_user_by_email(email=login.email)
    password_hash = user.password_hash if user is not None else DUMMY_PASSWORD_HASH

    # Checking a dummy hash prevents timing from revealing whether the account exists.
    if not check_password_hash(password_hash, login.password) or user is None:
        raise InvalidCredentialsError("Invalid email or password.")

    return str(
        create_access_token(
            identity=str(user.id),
            additional_claims={"role": user.role},
        )
    )
