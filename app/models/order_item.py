"""Order line database model."""

from typing import TYPE_CHECKING

from flask_sqlalchemy.model import Model
from sqlalchemy import Float, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from app.models.order import Order
else:
    from app.extensions import db

    Model = db.Model


class OrderItem(Model):
    """Persist a product line in an order."""

    __tablename__ = "order_item"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    commande_id: Mapped[int] = mapped_column(ForeignKey("order.id"), nullable=False)
    produit_id: Mapped[int] = mapped_column(ForeignKey("product.id"), nullable=False)
    quantite: Mapped[int] = mapped_column(Integer, nullable=False)
    prix_unitaire: Mapped[float] = mapped_column(Float, nullable=False)
    # Exposes the order linked by commande_id and stays synchronized with Order.lignes.
    commande: Mapped["Order"] = relationship(back_populates="lignes")

    def to_dict(self) -> dict[str, int | float]:
        """Return the public order line representation."""
        return {
            "id": self.id,
            "produit_id": self.produit_id,
            "quantite": self.quantite,
            "prix_unitaire": self.prix_unitaire,
        }
