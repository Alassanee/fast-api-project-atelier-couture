"""Schémas Pydantic des paiements (lecture ; création au palier 2, étape 10)."""

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict

from app.enums import ModePaiement


class PaiementRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    commande_id: int
    montant: int
    mode: ModePaiement
    reference: str | None
    date_paiement: date
    enregistre_par_id: int
    created_at: datetime
