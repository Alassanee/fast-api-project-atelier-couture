"""Logique métier des commandes (complétée au palier 2)."""

from datetime import date

from sqlalchemy import ColumnElement, and_

from app.enums import StatutCommande
from app.models import Commande
from app.schemas.commande import CommandeListe

STATUTS_FINAUX = (StatutCommande.livree, StatutCommande.annulee)


def est_en_retard(commande: Commande, aujourd_hui: date | None = None) -> bool:
    """RG11 : date prévue dépassée et commande ni livrée ni annulée."""
    aujourd_hui = aujourd_hui or date.today()
    return commande.date_livraison_prevue < aujourd_hui and commande.statut not in STATUTS_FINAUX


def condition_en_retard(aujourd_hui: date | None = None) -> ColumnElement[bool]:
    """RG11 traduite en condition SQL (filtres et statistiques)."""
    aujourd_hui = aujourd_hui or date.today()
    return and_(
        Commande.date_livraison_prevue < aujourd_hui,
        Commande.statut.not_in(STATUTS_FINAUX),
    )


def nom_client(commande: Commande) -> str:
    return f"{commande.client.prenom} {commande.client.nom}"


def vers_liste(commande: Commande) -> CommandeListe:
    return CommandeListe(
        id=commande.id,
        numero=commande.numero,
        client_id=commande.client_id,
        client_nom=nom_client(commande),
        statut=commande.statut,
        date_commande=commande.date_commande,
        date_livraison_prevue=commande.date_livraison_prevue,
        montant_total=commande.montant_total,
        montant_paye=commande.montant_paye,
        solde=commande.solde,
        en_retard=est_en_retard(commande),
    )
