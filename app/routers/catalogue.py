"""Routes du catalogue des prestations (14 à 17)."""

from typing import Annotated

from fastapi import APIRouter, Query, status

from app.dependencies import AdminSeulement, DbSession, UtilisateurCourant
from app.schemas.catalogue import TypeVetementCreate, TypeVetementRead, TypeVetementUpdate
from app.services import catalogue as service

router = APIRouter(prefix="/catalogue", tags=["Catalogue"])


@router.post(
    "", response_model=TypeVetementRead, status_code=status.HTTP_201_CREATED,
    summary="Ajouter une prestation (admin)",
)
def creer_prestation(donnees: TypeVetementCreate, db: DbSession, _: AdminSeulement):
    prestation = service.creer(db, donnees)
    db.commit()
    return prestation


@router.get("", response_model=list[TypeVetementRead], summary="Lister les prestations (triées par nom)")
def lister_prestations(
    db: DbSession,
    _: UtilisateurCourant,
    actifs_seulement: Annotated[
        bool, Query(description="false pour inclure les prestations retirées")
    ] = True,
):
    return service.lister(db, actifs_seulement=actifs_seulement)


@router.get("/{prestation_id}", response_model=TypeVetementRead, summary="Détail d'une prestation")
def obtenir_prestation(prestation_id: int, db: DbSession, _: UtilisateurCourant):
    return service.obtenir(db, prestation_id)


@router.patch(
    "/{prestation_id}", response_model=TypeVetementRead,
    summary="Modifier une prestation (admin) ; actif=false la retire",
)
def modifier_prestation(
    prestation_id: int, donnees: TypeVetementUpdate, db: DbSession, _: AdminSeulement
):
    prestation = service.modifier(db, prestation_id, donnees)
    db.commit()
    return prestation
