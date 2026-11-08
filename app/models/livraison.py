from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import Date, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.enums import ModeLivraison, StatutLivraison
from app.models.mixins import enum_type

if TYPE_CHECKING:
    from app.models.commande import Commande


class Livraison(Base):
    __tablename__ = "livraisons"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Une seule livraison par commande.
    commande_id: Mapped[int] = mapped_column(
        ForeignKey("commandes.id", ondelete="CASCADE"), unique=True
    )
    mode: Mapped[ModeLivraison] = mapped_column(enum_type(ModeLivraison, "mode_livraison"))
    adresse: Mapped[str | None] = mapped_column(String(255))
    livreur: Mapped[str | None] = mapped_column(String(150))
    date_prevue: Mapped[date] = mapped_column(Date, index=True)
    date_effective: Mapped[date | None] = mapped_column(Date)
    statut: Mapped[StatutLivraison] = mapped_column(
        enum_type(StatutLivraison, "statut_livraison"), default=StatutLivraison.planifiee
    )
    notes: Mapped[str | None] = mapped_column(Text)

    commande: Mapped["Commande"] = relationship(back_populates="livraison")
