"""Logique métier des paiements (RG16, RG17 ; routes 32 à 34)."""

from collections.abc import Sequence
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.enums import StatutCommande
from app.exceptions import Conflit, DonneesInvalides, NonTrouve
from app.models import Commande, Paiement, Utilisateur
from app.schemas.paiement import PaiementCreate


def _commande_verrouillee(db: Session, commande_id: int) -> Commande:
    """Verrouille la ligne de la commande (SELECT ... FOR UPDATE) : deux encaissements
    simultanés ne peuvent pas dépasser le solde."""
    commande = db.scalar(select(Commande).where(Commande.id == commande_id).with_for_update())
    if commande is None:
        raise NonTrouve(f"Commande {commande_id} introuvable.")
    return commande


def recalculer_paye(db: Session, commande: Commande) -> None:
    """Payé = somme des paiements de la commande (RG7, RG17)."""
    db.flush()
    commande.montant_paye = db.scalar(
        select(func.coalesce(func.sum(Paiement.montant), 0)).where(Paiement.commande_id == commande.id)
    )


def encaisser(db: Session, commande_id: int, donnees: PaiementCreate, auteur: Utilisateur) -> Paiement:
    commande = _commande_verrouillee(db, commande_id)

    # RG16 : refusé sur une commande annulée.
    if commande.statut == StatutCommande.annulee:
        raise Conflit(f"La commande {commande.numero} est annulée : aucun paiement n'est accepté.")
    # RG16 : pas de date future.
    date_paiement = donnees.date_paiement or date.today()
    if date_paiement > date.today():
        raise DonneesInvalides(f"La date de paiement ({date_paiement}) ne peut pas être dans le futur.")
    # RG16 : ne dépasse pas le solde restant.
    if donnees.montant > commande.solde:
        raise Conflit(
            f"Le paiement de {donnees.montant} FCFA dépasse le solde restant "
            f"de la commande {commande.numero} ({commande.solde} FCFA)."
        )

    paiement = Paiement(
        commande_id=commande.id,
        montant=donnees.montant,
        mode=donnees.mode,
        reference=(donnees.reference or "").strip() or None,
        date_paiement=date_paiement,
        enregistre_par_id=auteur.id,
    )
    db.add(paiement)
    recalculer_paye(db, commande)
    db.flush()
    return paiement


def lister(db: Session, commande_id: int) -> Sequence[Paiement]:
    """Paiements de la commande, dans l'ordre de saisie."""
    if db.get(Commande, commande_id) is None:
        raise NonTrouve(f"Commande {commande_id} introuvable.")
    return db.scalars(
        select(Paiement).where(Paiement.commande_id == commande_id).order_by(Paiement.id)
    ).all()


def annuler(db: Session, paiement_id: int) -> Commande:
    """RG17 : supprimer un paiement saisi par erreur recalcule le payé et le solde."""
    paiement = db.get(Paiement, paiement_id)
    if paiement is None:
        raise NonTrouve(f"Paiement {paiement_id} introuvable.")
    commande = _commande_verrouillee(db, paiement.commande_id)
    db.delete(paiement)
    recalculer_paye(db, commande)
    db.flush()
    return commande
