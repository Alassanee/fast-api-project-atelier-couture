"""Schémas Pydantic des livraisons."""

from datetime import date

from pydantic import BaseModel, ConfigDict, Field

from app.enums import ModeLivraison, StatutLivraison


class LivraisonPlanification(BaseModel):
    """Route 35 : planifier ou replanifier la livraison d'une commande."""

    mode: ModeLivraison
    date_prevue: date
    adresse: str | None = Field(default=None, max_length=255, description="Obligatoire à domicile (RG18)")
    livreur: str | None = Field(default=None, max_length=150)
    notes: str | None = None


class ConfirmationLivraison(BaseModel):
    """Route 37 : corps facultatif de la confirmation de livraison."""

    date_effective: date | None = Field(default=None, description="Aujourd'hui par défaut")
    autoriser_solde_impaye: bool = Field(
        default=False, description="Livrer malgré un solde impayé (la dette reste visible, RG19)"
    )


class LivraisonRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    commande_id: int
    mode: ModeLivraison
    adresse: str | None
    livreur: str | None
    date_prevue: date
    date_effective: date | None
    statut: StatutLivraison
    notes: str | None


class LivraisonTournee(LivraisonRead):
    """Route 38 : élément de la liste de tournée."""

    numero_commande: str | None
    client_nom: str
    client_telephone: str
    solde_commande: int
