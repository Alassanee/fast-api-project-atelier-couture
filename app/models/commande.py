from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.enums import StatutCommande
from app.models.mixins import TimestampMixin, enum_type

if TYPE_CHECKING:
    from app.models.client import Client
    from app.models.livraison import Livraison
    from app.models.mesure import Mesure
    from app.models.paiement import Paiement
    from app.models.type_vetement import TypeVetement
    from app.models.utilisateur import Utilisateur

statut_commande_type = enum_type(StatutCommande, "statut_commande")


class Commande(TimestampMixin, Base):
    __tablename__ = "commandes"

    id: Mapped[int] = mapped_column(primary_key=True)
    # CMD-AAAA-NNNNN (RG5) : rempli juste après l'insertion, une fois l'id connu.
    numero: Mapped[str | None] = mapped_column(String(20), unique=True, index=True)
    client_id: Mapped[int] = mapped_column(
        ForeignKey("clients.id", ondelete="RESTRICT"), index=True
    )
    mesure_id: Mapped[int | None] = mapped_column(ForeignKey("mesures.id", ondelete="RESTRICT"))
    statut: Mapped[StatutCommande] = mapped_column(
        statut_commande_type, default=StatutCommande.en_attente, index=True
    )
    date_commande: Mapped[date] = mapped_column(Date, index=True)
    date_livraison_prevue: Mapped[date] = mapped_column(Date)
    date_livraison_reelle: Mapped[date | None] = mapped_column(Date)
    remise: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    montant_total: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    montant_paye: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    notes: Mapped[str | None] = mapped_column(Text)
    cree_par_id: Mapped[int] = mapped_column(ForeignKey("utilisateurs.id"))

    client: Mapped["Client"] = relationship(back_populates="commandes")
    mesure: Mapped["Mesure | None"] = relationship()
    cree_par: Mapped["Utilisateur"] = relationship()
    lignes: Mapped[list["LigneCommande"]] = relationship(
        back_populates="commande", cascade="all, delete-orphan", order_by="LigneCommande.id"
    )
    paiements: Mapped[list["Paiement"]] = relationship(
        back_populates="commande", cascade="all, delete-orphan", order_by="Paiement.id"
    )
    historique: Mapped[list["HistoriqueStatut"]] = relationship(
        back_populates="commande",
        cascade="all, delete-orphan",
        order_by="HistoriqueStatut.id",
    )
    livraison: Mapped["Livraison | None"] = relationship(
        back_populates="commande", cascade="all, delete-orphan", uselist=False
    )

    @property
    def solde(self) -> int:
        """Solde = total − payé (RG7)."""
        return self.montant_total - self.montant_paye


class LigneCommande(Base):
    __tablename__ = "lignes_commande"

    id: Mapped[int] = mapped_column(primary_key=True)
    commande_id: Mapped[int] = mapped_column(
        ForeignKey("commandes.id", ondelete="CASCADE"), index=True
    )
    type_vetement_id: Mapped[int] = mapped_column(
        ForeignKey("types_vetement.id", ondelete="RESTRICT")
    )
    description: Mapped[str | None] = mapped_column(Text)
    quantite: Mapped[int] = mapped_column(Integer)
    prix_unitaire: Mapped[int] = mapped_column(Integer)  # FCFA

    commande: Mapped["Commande"] = relationship(back_populates="lignes")
    type_vetement: Mapped["TypeVetement"] = relationship()

    @property
    def sous_total(self) -> int:
        return self.quantite * self.prix_unitaire


class HistoriqueStatut(Base):
    __tablename__ = "historiques_statut"

    id: Mapped[int] = mapped_column(primary_key=True)
    commande_id: Mapped[int] = mapped_column(
        ForeignKey("commandes.id", ondelete="CASCADE"), index=True
    )
    # Vide pour la première ligne, inscrite à la création de la commande (RG15).
    ancien_statut: Mapped[StatutCommande | None] = mapped_column(
        enum_type(StatutCommande, "ancien_statut")
    )
    nouveau_statut: Mapped[StatutCommande] = mapped_column(
        enum_type(StatutCommande, "nouveau_statut")
    )
    commentaire: Mapped[str | None] = mapped_column(Text)
    utilisateur_id: Mapped[int] = mapped_column(ForeignKey("utilisateurs.id"))
    date_changement: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    commande: Mapped["Commande"] = relationship(back_populates="historique")
    utilisateur: Mapped["Utilisateur"] = relationship()
