"""Routes des paiements (32 à 34)."""

from fastapi import APIRouter, Response, status

from app.dependencies import Accueil, AdminSeulement, DbSession, UtilisateurCourant
from app.schemas.paiement import PaiementCreate, PaiementEnregistre, PaiementRead
from app.services import paiements as service

router = APIRouter(tags=["Paiements"])


@router.post(
    "/commandes/{commande_id}/paiements", response_model=PaiementEnregistre,
    status_code=status.HTTP_201_CREATED, summary="Encaisser un acompte ou le solde (accueil)",
)
def encaisser(commande_id: int, donnees: PaiementCreate, db: DbSession, auteur: Accueil):
    paiement = service.encaisser(db, commande_id, donnees, auteur)
    db.commit()
    solde = paiement.commande.solde
    return PaiementEnregistre(**PaiementRead.model_validate(paiement).model_dump(), solde_restant=solde)


@router.get(
    "/commandes/{commande_id}/paiements", response_model=list[PaiementRead],
    summary="Paiements de la commande (ordre de saisie)",
)
def lister_paiements(commande_id: int, db: DbSession, _: UtilisateurCourant):
    return service.lister(db, commande_id)


@router.delete(
    "/paiements/{paiement_id}", status_code=status.HTTP_204_NO_CONTENT,
    summary="Annuler un paiement saisi par erreur (admin)",
)
def annuler_paiement(paiement_id: int, db: DbSession, _: AdminSeulement) -> Response:
    service.annuler(db, paiement_id)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
