"""Logique métier du catalogue des prestations (routes 14 à 17)."""

from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.exceptions import Conflit, NonTrouve
from app.models import TypeVetement
from app.schemas.catalogue import TypeVetementCreate, TypeVetementUpdate


def _verifier_nom_libre(db: Session, nom: str, sauf_id: int | None = None) -> None:
    requete = select(TypeVetement.id).where(func.lower(TypeVetement.nom) == nom.lower())
    if sauf_id is not None:
        requete = requete.where(TypeVetement.id != sauf_id)
    if db.scalar(requete) is not None:
        raise Conflit(f"Une prestation nommée « {nom} » existe déjà dans le catalogue.")


def creer(db: Session, donnees: TypeVetementCreate) -> TypeVetement:
    _verifier_nom_libre(db, donnees.nom)
    prestation = TypeVetement(**donnees.model_dump(), actif=True)
    db.add(prestation)
    db.flush()
    return prestation


def lister(db: Session, *, actifs_seulement: bool = True) -> Sequence[TypeVetement]:
    requete = select(TypeVetement).order_by(TypeVetement.nom, TypeVetement.id)
    if actifs_seulement:
        requete = requete.where(TypeVetement.actif.is_(True))
    return db.scalars(requete).all()


def obtenir(db: Session, prestation_id: int) -> TypeVetement:
    prestation = db.get(TypeVetement, prestation_id)
    if prestation is None:
        raise NonTrouve(f"Prestation {prestation_id} introuvable dans le catalogue.")
    return prestation


def modifier(db: Session, prestation_id: int, donnees: TypeVetementUpdate) -> TypeVetement:
    """Les anciennes commandes ne sont jamais touchées : chaque ligne garde son
    propre prix_unitaire, et une prestation retirée (actif=false) reste liée."""
    prestation = obtenir(db, prestation_id)
    changements = donnees.model_dump(exclude_unset=True)
    if "nom" in changements:
        _verifier_nom_libre(db, changements["nom"], sauf_id=prestation.id)
    for champ, valeur in changements.items():
        setattr(prestation, champ, valeur)
    db.flush()
    return prestation
