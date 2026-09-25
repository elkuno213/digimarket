"""Order database model."""

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from flask_sqlalchemy.model import Model
from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from app.models.order_item import OrderItem
else:
    from app.extensions import db

    Model = db.Model


class Order(Model):
    """Persist a customer's order."""

    __tablename__ = "order"

    # Map the order header stored in the supplied schema.
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    utilisateur_id: Mapped[int] = mapped_column(ForeignKey("user.id"), nullable=False)
    date_commande: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    adresse_livraison: Mapped[str] = mapped_column(String(200), nullable=False)
    statut: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # Exposes lines linked by commande_id and stays synchronized with OrderItem.commande.
    lignes: Mapped[list["OrderItem"]] = relationship(back_populates="commande")

    def to_dict(self) -> dict[str, int | str | None]:
        """Return the public order representation with a UTC timestamp."""
        # Normalize an optional SQLite datetime before including it in JSON.
        date_commande = self.date_commande
        if date_commande is not None:
            if date_commande.tzinfo is None:
                date_commande = date_commande.replace(tzinfo=UTC)
            else:
                date_commande = date_commande.astimezone(UTC)

        return {
            "id": self.id,
            "utilisateur_id": self.utilisateur_id,
            "date_commande": date_commande.isoformat() if date_commande is not None else None,
            "adresse_livraison": self.adresse_livraison,
            "statut": self.statut,
        }
