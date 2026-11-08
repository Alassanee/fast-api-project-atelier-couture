"""Schémas Pydantic des commandes (complétés au palier 2)."""

from datetime import date

from pydantic import BaseModel

from app.enums import StatutCommande


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
