"""Routes des clients (7 à 13)."""

from typing import Annotated

from fastapi import APIRouter, Query, Response, status

from app.dependencies import AdminSeulement, DbSession, UtilisateurCourant
from app.enums import Genre
from app.schemas.client import ClientCreate, ClientRead, ClientResume, ClientUpdate
from app.schemas.commande import CommandeListe
from app.schemas.commun import Page, PaginationParams
from app.services import clients as service

router = APIRouter(prefix="/clients", tags=["Clients"])


@router.post(
    "", response_model=ClientRead, status_code=status.HTTP_201_CREATED,
    summary="Créer un client",
)
def creer_client(donnees: ClientCreate, db: DbSession, _: UtilisateurCourant):
    client = service.creer(db, donnees)
    db.commit()
    return client


@router.get("", response_model=Page[ClientRead], summary="Lister les clients (paginé)")
def lister_clients(
    db: DbSession,
    _: UtilisateurCourant,
    pagination: PaginationParams,
    q: Annotated[
        str | None,
        Query(min_length=2, description="Recherche dans nom, prénom et téléphone (2 caractères min.)"),
    ] = None,
    genre: Genre | None = None,
):
    items, total = service.lister(
        db, q=q, genre=genre, limit=pagination.limit, offset=pagination.offset
    )
    return Page[ClientRead](
        items=[ClientRead.model_validate(c) for c in items],
        total=total, limit=pagination.limit, offset=pagination.offset,
    )


@router.get("/{client_id}", response_model=ClientRead, summary="Fiche d'un client")
def obtenir_client(client_id: int, db: DbSession, _: UtilisateurCourant):
    return service.obtenir(db, client_id)


@router.patch("/{client_id}", response_model=ClientRead, summary="Modifier un client")
def modifier_client(client_id: int, donnees: ClientUpdate, db: DbSession, _: UtilisateurCourant):
    client = service.modifier(db, client_id, donnees)
    db.commit()
    db.refresh(client)
    return client


@router.delete(
    "/{client_id}", status_code=status.HTTP_204_NO_CONTENT,
    summary="Supprimer un client (admin)",
)
def supprimer_client(client_id: int, db: DbSession, _: AdminSeulement) -> Response:
    service.supprimer(db, client_id)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/{client_id}/commandes", response_model=Page[CommandeListe],
    summary="Commandes du client (la plus récente d'abord)",
)
def commandes_du_client(
    client_id: int, db: DbSession, _: UtilisateurCourant, pagination: PaginationParams
):
    items, total = service.commandes_du_client(
        db, client_id, limit=pagination.limit, offset=pagination.offset
    )
    return Page[CommandeListe](
        items=items, total=total, limit=pagination.limit, offset=pagination.offset
    )


@router.get("/{client_id}/resume", response_model=ClientResume, summary="Résumé d'un client")
def resume_client(client_id: int, db: DbSession, _: UtilisateurCourant):
    return service.resume(db, client_id)
