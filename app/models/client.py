from typing import TYPE_CHECKING

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.enums import Genre
from app.models.mixins import TimestampMixin, enum_type

if TYPE_CHECKING:
    from app.models.commande import Commande
    from app.models.mesure import Mesure


class Client(TimestampMixin, Base):
    __tablename__ = "clients"

    id: Mapped[int] = mapped_column(primary_key=True)
    nom: Mapped[str] = mapped_column(String(100), index=True)
    prenom: Mapped[str] = mapped_column(String(100))
    telephone: Mapped[str] = mapped_column(String(21), unique=True, index=True)
    email: Mapped[str | None] = mapped_column(String(255))
    adresse: Mapped[str | None] = mapped_column(String(255))
    genre: Mapped[Genre | None] = mapped_column(enum_type(Genre, "genre"))
    notes: Mapped[str | None] = mapped_column(Text)

    # Supprimer un client supprime ses mesures (route 11) ; les commandes bloquent (RG4).
    mesures: Mapped[list["Mesure"]] = relationship(
        back_populates="client", cascade="all, delete-orphan", passive_deletes=True
    )
    commandes: Mapped[list["Commande"]] = relationship(back_populates="client")
