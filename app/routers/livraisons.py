"""Routes des livraisons (35 à 38)."""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Body, Query

from app.dependencies import Accueil, DbSession, UtilisateurCourant
from app.enums import StatutLivraison
from app.schemas.commande import CommandeDetail
from app.schemas.livraison import (
    ConfirmationLivraison,
    LivraisonPlanification,
    LivraisonRead,
    LivraisonTournee,
)
from app.services import commandes as service_commandes
from app.services import livraisons as service

router = APIRouter(tags=["Livraisons"])


@router.put(
    "/commandes/{commande_id}/livraison", response_model=LivraisonRead,
    summary="Planifier ou replanifier la livraison (accueil)",
)
def planifier_livraison(
    commande_id: int, donnees: LivraisonPlanification, db: DbSession, _: Accueil
):
    livraison = service.planifier(db, commande_id, donnees)
    db.commit()
    return livraison


@router.get(
    "/commandes/{commande_id}/livraison", response_model=LivraisonRead,
    summary="Livraison de la commande",
)
def obtenir_livraison(commande_id: int, db: DbSession, _: UtilisateurCourant):
    return service.obtenir(db, commande_id)


@router.post(
    "/commandes/{commande_id}/livraison/confirmer", response_model=CommandeDetail,
    summary="Confirmer la remise du vêtement au client (accueil)",
)
def confirmer_livraison(
    commande_id: int,
    db: DbSession,
    acteur: Accueil,
    donnees: Annotated[ConfirmationLivraison | None, Body()] = None,
):
    service.confirmer(db, commande_id, donnees or ConfirmationLivraison(), acteur)
    db.commit()
    db.expire_all()
    return service_commandes.vers_detail(service_commandes.obtenir(db, commande_id))


@router.get(
    "/livraisons", response_model=list[LivraisonTournee],
    summary="Liste de tournée (triée par date prévue)",
)
def lister_livraisons(
    db: DbSession,
    _: UtilisateurCourant,
    statut: StatutLivraison | None = None,
    date_min: Annotated[date | None, Query(description="Date prévue minimale")] = None,
    date_max: Annotated[date | None, Query(description="Date prévue maximale")] = None,
):
    return service.tournee(db, statut=statut, date_min=date_min, date_max=date_max)
