"""Business logic for account registration and login."""

import re
from collections.abc import Mapping
from dataclasses import dataclass

from flask_jwt_extended import create_access_token
from sqlalchemy import text
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


class AdministratorAlreadyExistsError(ValueError):
    """Raised when trusted onboarding is attempted after an administrator exists."""


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
    return _require_nonblank_str(value, key)


def _require_nonblank_str(value: object, field_name: str) -> str:
    """Return one required text value while retaining public validation messages."""
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"{field_name} must be a nonblank string.")
    return value


def find_user_by_email(email: str) -> User | None:
    """Find a user by normalized email.

    Args:
        email: The normalized email address to look up.

    Returns:
        The matching user, if one exists.
    """
    # Build a typed lookup, then return at most one unique-email record.
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
    # Confirm JSON object shape, then map API field names into shared account validation.
    payload_json = require_json(payload=payload)
    return validate_account(
        email=payload_json.get("email"),
        name=payload_json.get("nom"),
        password=payload_json.get("mot_de_passe"),
    )


def validate_account(email: object, name: object, password: object) -> RegistrationData:
    """Validate and normalize the values needed to persist an account."""
    # Normalize text first so validation and uniqueness use canonical values.
    normalized_email = _require_nonblank_str(email, "email").strip().lower()
    normalized_name = _require_nonblank_str(name, "nom").strip()
    validated_password = _require_nonblank_str(password, "mot_de_passe")

    # Apply the rules shared by public registration and trusted onboarding.
    if EMAIL_PATTERN.fullmatch(normalized_email) is None:
        raise ValidationError("Email address is invalid.")
    if len(validated_password) < 8:
        raise ValidationError("Password must contain at least 8 characters.")

    return RegistrationData(
        email=normalized_email,
        name=normalized_name,
        password=validated_password,
    )


def register_user(registration: RegistrationData) -> User:
    """Persist a new client account.

    Args:
        registration: Validated values for the new account.

    Returns:
        The persisted client user.

    Raises:
        DuplicateEmailError: If the normalized email is already registered.
    """
    # Public registration always persists the least-privileged client role.
    return _persist_user(registration, role="client")


def _persist_user(registration: RegistrationData, role: str) -> User:
    """Persist one validated account and translate duplicate-email races."""

    # The raw password stays outside the model and is hashed before User construction.
    password_hash = generate_password_hash(registration.password)

    # add() stages the insert; commit() below makes the transaction permanent.
    user = User(
        email=registration.email,
        password_hash=password_hash,
        nom=registration.name,
        role=role,
    )
    db.session.add(user)

    try:
        db.session.commit()
    except IntegrityError:
        # The database unique constraint protects concurrent duplicate inserts.
        # A rollback resets this failed session before we return the public duplicate-email error.
        db.session.rollback()
        raise DuplicateEmailError("An account already exists for this email.") from None

    return user


def onboard_administrator(email: object, name: object, password: object) -> User:
    """Atomically create the first administrator from trusted local input."""
    # Validate before opening a write transaction so invalid input changes nothing.
    registration = validate_account(email, name, password)

    try:
        # SQLite locks competing writers before checking whether onboarding is still allowed.
        db.session.execute(text("BEGIN IMMEDIATE"))
        existing_admin = db.session.scalar(db.select(User).where(User.role == "admin"))
        if existing_admin is not None:
            raise AdministratorAlreadyExistsError("An administrator already exists.")
        return _persist_user(registration, role="admin")
    except Exception:
        # Roll back the explicit transaction before propagating every failure.
        db.session.rollback()
        raise


def validate_login(payload: object) -> LoginData:
    """Validate and normalize a login JSON payload.

    Args:
        payload: The decoded JSON value from the HTTP request.

    Returns:
        The validated login credentials.

    Raises:
        ValidationError: If the payload is not a valid login object.
    """
    # Confirm JSON object shape, then normalize credentials used for account lookup.
    payload_json = require_json(payload=payload)
    email = require_str(payload_json, "email").strip().lower()
    password = require_str(payload=payload_json, key="mot_de_passe")

    # Reject a malformed email before password verification begins.
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
    # Validate input, then load the account using its normalized email.
    login = validate_login(payload=payload)
    user = find_user_by_email(email=login.email)
    password_hash = user.password_hash if user is not None else DUMMY_PASSWORD_HASH

    # Checking a dummy hash prevents timing from revealing whether the account exists.
    if not check_password_hash(password_hash, login.password) or user is None:
        raise InvalidCredentialsError("Invalid email or password.")

    # Put only stable identity and authorization data in the signed access token.
    return str(
        create_access_token(
            identity=str(user.id),
            additional_claims={"role": user.role},
        )
    )
