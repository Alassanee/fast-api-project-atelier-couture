"""Statistiques (routes 39 à 43) : administrateur uniquement."""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Query

from app.dependencies import AdminSeulement, DbSession
from app.schemas.commande import CommandeListe
from app.schemas.commun import Page, PaginationParams
from app.schemas.statistiques import (
    ChiffreAffaires,
    Granularite,
    StatTypeVetement,
    TableauDeBord,
    TopClient,
)
from app.services import statistiques as service

router = APIRouter(prefix="/statistiques", tags=["Statistiques"])

DateDebut = Annotated[date | None, Query(description="Par défaut : 1er du mois courant")]
DateFin = Annotated[date | None, Query(description="Par défaut : aujourd'hui")]


@router.get("/tableau-de-bord", response_model=TableauDeBord, summary="Tableau de bord du mois")
def tableau_de_bord(db: DbSession, _: AdminSeulement):
    return service.tableau_de_bord(db)


@router.get(
    "/chiffre-affaires", response_model=ChiffreAffaires,
    summary="Chiffre d'affaires et encaissements par jour ou par mois",
)
def chiffre_affaires(
    db: DbSession,
    _: AdminSeulement,
    granularite: Granularite = Granularite.jour,
    date_debut: DateDebut = None,
    date_fin: DateFin = None,
):
    return service.chiffre_affaires(db, granularite, date_debut, date_fin)


@router.get(
    "/types-vetement", response_model=list[StatTypeVetement],
    summary="Quantités et chiffre d'affaires (avant remise) par type de vêtement",
)
def types_vetement(db: DbSession, _: AdminSeulement, date_debut: DateDebut = None, date_fin: DateFin = None):
    return service.par_type_vetement(db, date_debut, date_fin)


@router.get("/top-clients", response_model=list[TopClient], summary="Meilleurs clients de la période")
def top_clients(
    db: DbSession,
    _: AdminSeulement,
    date_debut: DateDebut = None,
    date_fin: DateFin = None,
    limite: Annotated[int, Query(ge=1, le=100)] = 10,
):
    return service.top_clients(db, date_debut, date_fin, limite)


@router.get(
    "/impayes", response_model=Page[CommandeListe],
    summary="Commandes non soldées, les plus urgentes d'abord",
)
def impayes(db: DbSession, _: AdminSeulement, pagination: PaginationParams):
    items, total = service.impayes(db, limit=pagination.limit, offset=pagination.offset)
    return Page[CommandeListe](items=items, total=total, limit=pagination.limit, offset=pagination.offset)
