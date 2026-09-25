"""User database model."""

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from flask_sqlalchemy.model import Model
from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

if not TYPE_CHECKING:
    from app.extensions import db

    Model = db.Model


class User(Model):
    """Persist an authenticated DigiMarket user."""

    __tablename__ = "user"

    # Map the supplied user table; password_hash stays private and is never serialized.
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(256), nullable=False)
    nom: Mapped[str] = mapped_column(String(100), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    date_creation: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(UTC),
    )

    def to_dict(self) -> dict[str, int | str]:
        """Return the public user representation with UTC creation time."""
        # SQLite reloads datetimes without timezone data, so normalize before serialization.
        date_creation = self.date_creation
        if date_creation.tzinfo is None:
            date_creation = date_creation.replace(tzinfo=UTC)
        else:
            date_creation = date_creation.astimezone(UTC)

        # Return only fields that are safe to expose in API responses.
        return {
            "id": self.id,
            "email": self.email,
            "nom": self.nom,
            "role": self.role,
            "date_creation": date_creation.isoformat(),
        }
