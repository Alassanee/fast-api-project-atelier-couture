"""Schémas Pydantic des livraisons (lecture ; planification au palier 3)."""

from datetime import date

from pydantic import BaseModel, ConfigDict

from app.enums import ModeLivraison, StatutLivraison


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
