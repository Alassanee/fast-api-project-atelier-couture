"""Schémas Pydantic des statistiques (administrateur uniquement, routes 39 à 43)."""

from datetime import date
from enum import StrEnum

from pydantic import BaseModel

from app.enums import StatutCommande
from app.schemas.commande import CommandeListe
from app.schemas.livraison import LivraisonTournee


class Granularite(StrEnum):
    jour = "jour"
    mois = "mois"


class TableauDeBord(BaseModel):
    """Route 39. Les trois premiers indicateurs portent sur le mois courant."""

    mois: str  # AAAA-MM
    chiffre_affaires_mois: int
    encaisse_mois: int
    nb_commandes_mois: int
    reste_a_encaisser: int
    commandes_par_statut: dict[StatutCommande, int]
    nb_commandes_en_retard: int
    commandes_pretes_a_livrer: list[CommandeListe]
    livraisons_du_jour: list[LivraisonTournee]


class PeriodeChiffreAffaires(BaseModel):
    periode: str  # AAAA-MM-JJ (jour) ou AAAA-MM (mois)
    chiffre_affaires: int
    encaisse: int


class ChiffreAffaires(BaseModel):
    """Route 40."""

    granularite: Granularite
    date_debut: date
    date_fin: date
    total_chiffre_affaires: int
    total_encaisse: int
    periodes: list[PeriodeChiffreAffaires]


class StatTypeVetement(BaseModel):
    """Route 41 : chiffre d'affaires avant remise."""

    type_vetement_id: int
    nom: str
    quantite_vendue: int
    chiffre_affaires: int


class TopClient(BaseModel):
    """Route 42."""

    client_id: int
    client_nom: str
    telephone: str
    nb_commandes: int
    chiffre_affaires: int
    solde_du: int
