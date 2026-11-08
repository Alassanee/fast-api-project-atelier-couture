"""Schémas Pydantic des commandes, lignes et historique des statuts."""

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.enums import StatutCommande
from app.schemas.livraison import LivraisonRead
from app.schemas.paiement import PaiementRead

# --- Lignes ----------------------------------------------------------------------


class LigneCreate(BaseModel):
    type_vetement_id: int
    description: str | None = None
    quantite: int = Field(default=1, ge=1, le=1000)
    prix_unitaire: int | None = Field(
        default=None, gt=0,
        description="Prix négocié en FCFA ; par défaut le prix de base du catalogue (RG6)",
    )


class LigneRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    type_vetement_id: int
    type_vetement_nom: str
    description: str | None
    quantite: int
    prix_unitaire: int
    sous_total: int


# --- Commandes ---------------------------------------------------------------------


class CommandeCreate(BaseModel):
    client_id: int
    mesure_id: int | None = Field(
        default=None, description="Par défaut : les dernières mesures du client (RG9)"
    )
    lignes: list[LigneCreate] = Field(min_length=1)
    remise: int = Field(default=0, ge=0, description="En FCFA")
    date_livraison_prevue: date | None = Field(
        default=None, description="Par défaut : date de commande + plus long délai (RG8)"
    )
    notes: str | None = None


class CommandeUpdate(BaseModel):
    """PATCH : seuls les champs envoyés sont modifiés ; les montants sont recalculés."""

    mesure_id: int | None = None
    date_livraison_prevue: date | None = None
    remise: int | None = Field(default=None, ge=0)
    notes: str | None = None

    @model_validator(mode="after")
    def _pas_de_null(self) -> "CommandeUpdate":
        for champ in ("date_livraison_prevue", "remise"):
            if champ in self.model_fields_set and getattr(self, champ) is None:
                raise ValueError(f"le champ « {champ} » ne peut pas être vide")
        return self


class ChangementStatut(BaseModel):
    statut: StatutCommande
    commentaire: str | None = None


class CommandeListe(BaseModel):
    """Élément d'une liste de commandes (routes 12 et 25)."""

    id: int
    numero: str | None
    client_id: int
    client_nom: str
    statut: StatutCommande
    date_commande: date
    date_livraison_prevue: date
    montant_total: int
    montant_paye: int
    solde: int
    en_retard: bool


class CommandeDetail(BaseModel):
    """Détail complet d'une commande (route 26)."""

    id: int
    numero: str | None
    client_id: int
    client_nom: str
    mesure_id: int | None
    statut: StatutCommande
    date_commande: date
    date_livraison_prevue: date
    date_livraison_reelle: date | None
    remise: int
    montant_total: int
    montant_paye: int
    solde: int
    en_retard: bool
    notes: str | None
    cree_par_id: int
    created_at: datetime
    updated_at: datetime
    lignes: list[LigneRead]
    paiements: list[PaiementRead]
    livraison: LivraisonRead | None


class HistoriqueRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    commande_id: int
    ancien_statut: StatutCommande | None
    nouveau_statut: StatutCommande
    commentaire: str | None
    utilisateur_id: int
    utilisateur_nom: str
    date_changement: datetime
