"""Logique métier des comptes utilisateurs."""

from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.enums import Role
from app.exceptions import Conflit, NonTrouve
from app.models import Utilisateur
from app.schemas.utilisateur import UtilisateurCreate, UtilisateurUpdate
from app.security import hacher_mot_de_passe


def _email_existe(db: Session, email: str) -> bool:
    return db.scalar(
        select(func.count()).select_from(Utilisateur).where(func.lower(Utilisateur.email) == email.lower())
    ) > 0


def creer(db: Session, donnees: UtilisateurCreate) -> Utilisateur:
    if _email_existe(db, donnees.email):
        raise Conflit(f"Un compte existe déjà avec l'e-mail « {donnees.email} ».")
    utilisateur = Utilisateur(
        email=donnees.email,
        nom_complet=donnees.nom_complet,
        mot_de_passe_hash=hacher_mot_de_passe(donnees.mot_de_passe),
        role=donnees.role,
        actif=True,
    )
    db.add(utilisateur)
    db.flush()
    return utilisateur


def lister(db: Session) -> Sequence[Utilisateur]:
    return db.scalars(select(Utilisateur).order_by(Utilisateur.nom_complet, Utilisateur.id)).all()


def obtenir(db: Session, utilisateur_id: int) -> Utilisateur:
    utilisateur = db.get(Utilisateur, utilisateur_id)
    if utilisateur is None:
        raise NonTrouve(f"Utilisateur {utilisateur_id} introuvable.")
    return utilisateur


def modifier(
    db: Session, utilisateur_id: int, donnees: UtilisateurUpdate, acteur: Utilisateur
) -> Utilisateur:
    utilisateur = obtenir(db, utilisateur_id)
    changements = donnees.model_dump(exclude_unset=True)

    # RG24 : un administrateur ne peut ni se désactiver ni retirer son propre rôle admin.
    if utilisateur.id == acteur.id:
        if changements.get("actif") is False:
            raise Conflit("Vous ne pouvez pas désactiver votre propre compte.")
        if "role" in changements and changements["role"] != Role.admin:
            raise Conflit("Vous ne pouvez pas retirer votre propre rôle d'administrateur.")

    if "mot_de_passe" in changements:
        utilisateur.mot_de_passe_hash = hacher_mot_de_passe(changements.pop("mot_de_passe"))
    if "nom_complet" in changements:
        changements["nom_complet"] = changements["nom_complet"].strip()
    for champ, valeur in changements.items():
        setattr(utilisateur, champ, valeur)
    db.flush()
    return utilisateur
