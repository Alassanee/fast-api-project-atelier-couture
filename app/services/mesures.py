"""Logique métier des prises de mesures (RG2, RG3, RG4 ; routes 18 à 23)."""

from collections.abc import Sequence
from datetime import date

from sqlalchemy import exists, select
from sqlalchemy.orm import Session

from app.exceptions import Conflit, DonneesInvalides, NonTrouve
from app.models import Commande, Mesure, Utilisateur
from app.schemas.mesure import MESSAGE_AUCUNE_MESURE, MesureCreate, MesureUpdate, a_au_moins_une_mesure
from app.services import clients as service_clients

# RG3 : la prise la plus récente est celle de date la plus récente
# (à date égale, la dernière saisie).
ORDRE_RECENT = (Mesure.date_prise.desc(), Mesure.id.desc())


def creer(db: Session, client_id: int, donnees: MesureCreate, auteur: Utilisateur) -> Mesure:
    service_clients.obtenir(db, client_id)
    valeurs = donnees.model_dump()
    valeurs["date_prise"] = donnees.date_prise or date.today()
    mesure = Mesure(**valeurs, client_id=client_id, prise_par_id=auteur.id)
    db.add(mesure)
    db.flush()
    return mesure


def historique(db: Session, client_id: int) -> Sequence[Mesure]:
    """RG3 : toutes les prises sont conservées, la plus récente d'abord."""
    service_clients.obtenir(db, client_id)
    return db.scalars(select(Mesure).where(Mesure.client_id == client_id).order_by(*ORDRE_RECENT)).all()


def dernieres(db: Session, client_id: int) -> Mesure | None:
    return db.scalar(
        select(Mesure).where(Mesure.client_id == client_id).order_by(*ORDRE_RECENT).limit(1)
    )


def obtenir_dernieres(db: Session, client_id: int) -> Mesure:
    service_clients.obtenir(db, client_id)
    mesure = dernieres(db, client_id)
    if mesure is None:
        raise NonTrouve(f"Le client {client_id} n'a aucune prise de mesures.")
    return mesure


def obtenir(db: Session, mesure_id: int) -> Mesure:
    mesure = db.get(Mesure, mesure_id)
    if mesure is None:
        raise NonTrouve(f"Prise de mesures {mesure_id} introuvable.")
    return mesure


def modifier(db: Session, mesure_id: int, donnees: MesureUpdate) -> Mesure:
    mesure = obtenir(db, mesure_id)
    for champ, valeur in donnees.model_dump(exclude_unset=True).items():
        setattr(mesure, champ, valeur)
    # RG2 : la correction ne doit pas supprimer toutes les mesures.
    if not a_au_moins_une_mesure(mesure):
        raise DonneesInvalides(f"Correction refusée : {MESSAGE_AUCUNE_MESURE}.")
    db.flush()
    return mesure


def supprimer(db: Session, mesure_id: int) -> None:
    """RG4 : des mesures utilisées par une commande ne peuvent pas être supprimées."""
    mesure = obtenir(db, mesure_id)
    if db.scalar(select(exists().where(Commande.mesure_id == mesure.id))):
        raise Conflit("Impossible de supprimer ces mesures : elles sont utilisées par une commande.")
    db.delete(mesure)
    db.flush()
