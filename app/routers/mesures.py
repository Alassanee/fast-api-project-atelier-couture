"""Routes des prises de mesures (18 à 23)."""

from fastapi import APIRouter, Response, status

from app.dependencies import DbSession, Tailleur, UtilisateurCourant
from app.schemas.mesure import MesureCreate, MesureRead, MesureUpdate
from app.services import mesures as service

router = APIRouter(tags=["Mesures"])


@router.post(
    "/clients/{client_id}/mesures", response_model=MesureRead,
    status_code=status.HTTP_201_CREATED, summary="Nouvelle prise de mesures (tailleur)",
)
def creer_mesure(client_id: int, donnees: MesureCreate, db: DbSession, tailleur: Tailleur):
    mesure = service.creer(db, client_id, donnees, auteur=tailleur)
    db.commit()
    return mesure


@router.get(
    "/clients/{client_id}/mesures", response_model=list[MesureRead],
    summary="Historique des mesures (la plus récente d'abord)",
)
def historique_mesures(client_id: int, db: DbSession, _: UtilisateurCourant):
    return service.historique(db, client_id)


@router.get(
    "/clients/{client_id}/mesures/derniere", response_model=MesureRead,
    summary="Dernières mesures du client",
)
def dernieres_mesures(client_id: int, db: DbSession, _: UtilisateurCourant):
    return service.obtenir_dernieres(db, client_id)


@router.get("/mesures/{mesure_id}", response_model=MesureRead, summary="Une prise de mesures")
def obtenir_mesure(mesure_id: int, db: DbSession, _: UtilisateurCourant):
    return service.obtenir(db, mesure_id)


@router.patch(
    "/mesures/{mesure_id}", response_model=MesureRead,
    summary="Corriger une prise de mesures (tailleur)",
)
def modifier_mesure(mesure_id: int, donnees: MesureUpdate, db: DbSession, _: Tailleur):
    mesure = service.modifier(db, mesure_id, donnees)
    db.commit()
    return mesure


@router.delete(
    "/mesures/{mesure_id}", status_code=status.HTTP_204_NO_CONTENT,
    summary="Supprimer une prise de mesures (tailleur)",
)
def supprimer_mesure(mesure_id: int, db: DbSession, _: Tailleur) -> Response:
    service.supprimer(db, mesure_id)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
