"""Routes des commandes (24 à 31)."""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Query, status

from app.dependencies import Accueil, DbSession, UtilisateurCourant
from app.enums import StatutCommande
from app.schemas.commande import (
    ChangementStatut,
    CommandeCreate,
    CommandeDetail,
    CommandeListe,
    CommandeUpdate,
    HistoriqueRead,
    LigneCreate,
)
from app.schemas.commun import Page, PaginationParams
from app.services import commandes as service

router = APIRouter(prefix="/commandes", tags=["Commandes"])


def _detail(db: DbSession, commande_id: int) -> CommandeDetail:
    db.expire_all()  # relit l'état validé (montants, lignes, horodatage)
    return service.vers_detail(service.obtenir(db, commande_id))


@router.post(
    "", response_model=CommandeDetail, status_code=status.HTTP_201_CREATED,
    summary="Créer une commande (accueil)",
)
def creer_commande(donnees: CommandeCreate, db: DbSession, auteur: Accueil):
    commande = service.creer(db, donnees, auteur)
    db.commit()
    return _detail(db, commande.id)


@router.get("", response_model=Page[CommandeListe], summary="Lister les commandes (paginé)")
def lister_commandes(
    db: DbSession,
    _: UtilisateurCourant,
    pagination: PaginationParams,
    statut: StatutCommande | None = None,
    client_id: int | None = None,
    en_retard: Annotated[bool | None, Query(description="RG11")] = None,
    date_min: Annotated[date | None, Query(description="Date de commande minimale")] = None,
    date_max: Annotated[date | None, Query(description="Date de commande maximale")] = None,
    numero: str | None = None,
):
    items, total = service.lister(
        db, statut=statut, client_id=client_id, en_retard=en_retard,
        date_min=date_min, date_max=date_max, numero=numero,
        limit=pagination.limit, offset=pagination.offset,
    )
    return Page[CommandeListe](items=items, total=total, limit=pagination.limit, offset=pagination.offset)


@router.get("/{commande_id}", response_model=CommandeDetail, summary="Détail d'une commande")
def obtenir_commande(commande_id: int, db: DbSession, _: UtilisateurCourant):
    return service.vers_detail(service.obtenir(db, commande_id))


@router.patch("/{commande_id}", response_model=CommandeDetail, summary="Modifier une commande (accueil)")
def modifier_commande(commande_id: int, donnees: CommandeUpdate, db: DbSession, _: Accueil):
    service.modifier(db, commande_id, donnees)
    db.commit()
    return _detail(db, commande_id)


@router.post(
    "/{commande_id}/statut", response_model=CommandeDetail,
    summary="Changer le statut (workflow, RG13 à RG15)",
)
def changer_statut(
    commande_id: int, donnees: ChangementStatut, db: DbSession, utilisateur: UtilisateurCourant
):
    service.changer_statut(db, commande_id, donnees, acteur=utilisateur)
    db.commit()
    return _detail(db, commande_id)


@router.get(
    "/{commande_id}/historique", response_model=list[HistoriqueRead],
    summary="Historique des changements de statut",
)
def historique_commande(commande_id: int, db: DbSession, _: UtilisateurCourant):
    return service.historique(db, commande_id)


@router.post(
    "/{commande_id}/lignes", response_model=CommandeDetail,
    status_code=status.HTTP_201_CREATED, summary="Ajouter une prestation (accueil, RG10)",
)
def ajouter_ligne(commande_id: int, donnees: LigneCreate, db: DbSession, _: Accueil):
    service.ajouter_ligne(db, commande_id, donnees)
    db.commit()
    return _detail(db, commande_id)


@router.delete(
    "/{commande_id}/lignes/{ligne_id}", response_model=CommandeDetail,
    summary="Retirer une prestation (accueil, RG10)",
)
def supprimer_ligne(commande_id: int, ligne_id: int, db: DbSession, _: Accueil):
    service.supprimer_ligne(db, commande_id, ligne_id)
    db.commit()
    return _detail(db, commande_id)
