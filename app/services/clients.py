"""Logique métier des clients (RG1, RG4, routes 7 à 13)."""

import re

from sqlalchemy import exists, func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.enums import Genre, StatutCommande
from app.exceptions import Conflit, DonneesInvalides, NonTrouve
from app.models import Client, Commande, Mesure
from app.schemas.client import ClientCreate, ClientResume, ClientUpdate
from app.schemas.commande import CommandeListe
from app.services import commandes as service_commandes

_SEPARATEURS = re.compile(r"[\s.\-()]")
_FORME_VALIDE = re.compile(r"^\+?\d{6,20}$")


def normaliser_telephone(telephone: str) -> str:
    """RG1 : supprime espaces, points, tirets et parenthèses puis vérifie la forme.

    « 77 123 45 67 » et « 771234567 » donnent le même numéro.
    """
    normalise = _SEPARATEURS.sub("", telephone or "")
    if not _FORME_VALIDE.fullmatch(normalise):
        raise DonneesInvalides(
            f"Numéro de téléphone invalide : « {telephone} ». Forme attendue : "
            "6 à 20 chiffres, avec un « + » initial facultatif."
        )
    return normalise


def _verifier_telephone_libre(db: Session, telephone: str, sauf_id: int | None = None) -> None:
    requete = select(Client.id).where(Client.telephone == telephone)
    if sauf_id is not None:
        requete = requete.where(Client.id != sauf_id)
    if db.scalar(requete) is not None:
        raise Conflit(f"Un client existe déjà avec le téléphone « {telephone} ».")


def obtenir(db: Session, client_id: int) -> Client:
    client = db.get(Client, client_id)
    if client is None:
        raise NonTrouve(f"Client {client_id} introuvable.")
    return client


def creer(db: Session, donnees: ClientCreate) -> Client:
    valeurs = donnees.model_dump()
    valeurs["telephone"] = normaliser_telephone(donnees.telephone)
    _verifier_telephone_libre(db, valeurs["telephone"])
    client = Client(**valeurs)
    db.add(client)
    db.flush()
    return client


def lister(
    db: Session, *, q: str | None, genre: Genre | None, limit: int, offset: int
) -> tuple[list[Client], int]:
    requete = select(Client)
    if q:
        motif = f"%{q.strip()}%"
        conditions = [
            Client.nom.ilike(motif),
            Client.prenom.ilike(motif),
            Client.telephone.ilike(motif),
            (Client.prenom + " " + Client.nom).ilike(motif),
            (Client.nom + " " + Client.prenom).ilike(motif),
        ]
        # « 77 123 » doit retrouver le numéro enregistré « 771234567 ».
        chiffres = _SEPARATEURS.sub("", q)
        if chiffres and chiffres != q.strip():
            conditions.append(Client.telephone.ilike(f"%{chiffres}%"))
        requete = requete.where(or_(*conditions))
    if genre is not None:
        requete = requete.where(Client.genre == genre)

    total = db.scalar(select(func.count()).select_from(requete.subquery()))
    clients = db.scalars(
        requete.order_by(Client.nom, Client.prenom, Client.id).limit(limit).offset(offset)
    ).all()
    return list(clients), total or 0


def modifier(db: Session, client_id: int, donnees: ClientUpdate) -> Client:
    client = obtenir(db, client_id)
    changements = donnees.model_dump(exclude_unset=True)
    if "telephone" in changements:
        changements["telephone"] = normaliser_telephone(changements["telephone"])
        # Garder son propre numéro n'est pas un doublon.
        _verifier_telephone_libre(db, changements["telephone"], sauf_id=client.id)
    for champ, valeur in changements.items():
        setattr(client, champ, valeur)
    db.flush()
    return client


def supprimer(db: Session, client_id: int) -> None:
    """RG4 : refusé (409) si le client a des commandes ; ses mesures sont supprimées."""
    client = obtenir(db, client_id)
    if db.scalar(select(exists().where(Commande.client_id == client.id))):
        raise Conflit(
            "Impossible de supprimer ce client : il a des commandes enregistrées."
        )
    db.delete(client)
    db.flush()


def commandes_du_client(
    db: Session, client_id: int, *, limit: int, offset: int
) -> tuple[list[CommandeListe], int]:
    obtenir(db, client_id)
    filtre = Commande.client_id == client_id
    total = db.scalar(select(func.count()).select_from(Commande).where(filtre)) or 0
    commandes = db.scalars(
        select(Commande)
        .options(joinedload(Commande.client))
        .where(filtre)
        .order_by(Commande.date_commande.desc(), Commande.id.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    return [service_commandes.vers_liste(c) for c in commandes], total


def resume(db: Session, client_id: int) -> ClientResume:
    """Route 13 : synthèse du client, commandes annulées exclues."""
    obtenir(db, client_id)
    non_annulees = (Commande.client_id == client_id) & (Commande.statut != StatutCommande.annulee)
    nb, chiffre_affaires, total_paye = db.execute(
        select(
            func.count(Commande.id),
            func.coalesce(func.sum(Commande.montant_total), 0),
            func.coalesce(func.sum(Commande.montant_paye), 0),
        ).where(non_annulees)
    ).one()
    derniere = db.scalar(
        select(Commande)
        .options(joinedload(Commande.client))
        .where(non_annulees)
        .order_by(Commande.date_commande.desc(), Commande.id.desc())
        .limit(1)
    )
    a_des_mesures = db.scalar(select(exists().where(Mesure.client_id == client_id)))
    return ClientResume(
        nb_commandes=nb,
        chiffre_affaires=chiffre_affaires,
        total_paye=total_paye,
        solde_du=chiffre_affaires - total_paye,
        derniere_commande=service_commandes.vers_liste(derniere) if derniere else None,
        a_des_mesures=bool(a_des_mesures),
    )
