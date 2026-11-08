from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import Date, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.enums import ModePaiement
from app.models.mixins import CreatedAtMixin, enum_type

if TYPE_CHECKING:
    from app.models.commande import Commande
    from app.models.utilisateur import Utilisateur


class Paiement(CreatedAtMixin, Base):
    __tablename__ = "paiements"

    id: Mapped[int] = mapped_column(primary_key=True)
    commande_id: Mapped[int] = mapped_column(
        ForeignKey("commandes.id", ondelete="CASCADE"), index=True
    )
    montant: Mapped[int] = mapped_column(Integer)  # FCFA
    mode: Mapped[ModePaiement] = mapped_column(enum_type(ModePaiement, "mode_paiement"))
    reference: Mapped[str | None] = mapped_column(String(100))
    date_paiement: Mapped[date] = mapped_column(Date, index=True)
    enregistre_par_id: Mapped[int] = mapped_column(ForeignKey("utilisateurs.id"))

    commande: Mapped["Commande"] = relationship(back_populates="paiements")
    enregistre_par: Mapped["Utilisateur"] = relationship()
