"""Service d'authentification."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Utilisateur
from app.security import verifier_mot_de_passe

# Même message que l'e-mail soit inconnu, le mot de passe faux ou le compte
# désactivé : on ne révèle pas quels comptes existent (RG23).
MESSAGE_ECHEC_CONNEXION = "E-mail ou mot de passe incorrect."


def authentifier(db: Session, email: str, mot_de_passe: str) -> Utilisateur | None:
    utilisateur = db.scalar(
        select(Utilisateur).where(func.lower(Utilisateur.email) == email.strip().lower())
    )
    # La vérification est faite même si l'utilisateur est inconnu (temps constant).
    hash_ = utilisateur.mot_de_passe_hash if utilisateur else None
    if not verifier_mot_de_passe(mot_de_passe, hash_):
        return None
    if utilisateur is None or not utilisateur.actif:
        return None
    return utilisateur
