"""Gestion des comptes (routes 3 à 6) : administrateur uniquement."""

from fastapi import APIRouter, status

from app.dependencies import AdminSeulement, DbSession
from app.schemas.utilisateur import UtilisateurCreate, UtilisateurRead, UtilisateurUpdate
from app.services import utilisateurs as service

router = APIRouter(prefix="/utilisateurs", tags=["Utilisateurs"])


@router.post(
    "", response_model=UtilisateurRead, status_code=status.HTTP_201_CREATED,
    summary="Créer un compte",
)
def creer_utilisateur(donnees: UtilisateurCreate, db: DbSession, _: AdminSeulement):
    utilisateur = service.creer(db, donnees)
    db.commit()
    return utilisateur


@router.get("", response_model=list[UtilisateurRead], summary="Lister les comptes (triés par nom)")
def lister_utilisateurs(db: DbSession, _: AdminSeulement):
    return service.lister(db)


@router.get("/{utilisateur_id}", response_model=UtilisateurRead, summary="Détail d'un compte")
def obtenir_utilisateur(utilisateur_id: int, db: DbSession, _: AdminSeulement):
    return service.obtenir(db, utilisateur_id)


@router.patch("/{utilisateur_id}", response_model=UtilisateurRead, summary="Modifier un compte")
def modifier_utilisateur(
    utilisateur_id: int, donnees: UtilisateurUpdate, db: DbSession, admin: AdminSeulement
):
    utilisateur = service.modifier(db, utilisateur_id, donnees, acteur=admin)
    db.commit()
    return utilisateur
