"""Product database model."""

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from flask_sqlalchemy.model import Model
from sqlalchemy import DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

if not TYPE_CHECKING:
    from app.extensions import db

    Model = db.Model


class Product(Model):
    """Persist a DigiMarket product."""

    __tablename__ = "product"

    # Map the supplied product fields, including nullable fields kept by the database schema.
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nom: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    categorie: Mapped[str] = mapped_column(String(50), nullable=False)
    prix: Mapped[float] = mapped_column(Float, nullable=False)
    quantite_stock: Mapped[int | None] = mapped_column(Integer, nullable=True)
    date_creation: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(UTC),
    )

    def to_dict(self) -> dict[str, int | float | str | None]:
        """Return the public product representation with UTC creation time."""
        # SQLite reloads datetimes without timezone data, so normalize before serialization.
        date_creation = self.date_creation
        if date_creation.tzinfo is None:
            date_creation = date_creation.replace(tzinfo=UTC)
        else:
            date_creation = date_creation.astimezone(UTC)

        # Return product fields in the API representation.
        return {
            "id": self.id,
            "nom": self.nom,
            "description": self.description,
            "categorie": self.categorie,
            "prix": self.prix,
            "quantite_stock": self.quantite_stock,
            "date_creation": date_creation.isoformat(),
        }
