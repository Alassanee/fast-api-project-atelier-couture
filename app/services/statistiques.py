"""Statistiques du patron (routes 39 à 43).

Définitions (section 6) :
- chiffre d'affaires : total des commandes non annulées, daté à la date de commande ;
- encaissé : total des paiements reçus, daté à la date de paiement ;
- reste à encaisser : somme des soldes des commandes non annulées.
"""

from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.enums import StatutCommande
from app.exceptions import DonneesInvalides
from app.models import Client, Commande, LigneCommande, Livraison, Paiement, TypeVetement
from app.schemas.commande import CommandeListe
from app.schemas.statistiques import (
    ChiffreAffaires,
    Granularite,
    PeriodeChiffreAffaires,
    StatTypeVetement,
    TableauDeBord,
    TopClient,
)
from app.services import commandes as service_commandes
from app.services import livraisons as service_livraisons

NON_ANNULEE = Commande.statut != StatutCommande.annulee


def periode_par_defaut(date_debut: date | None, date_fin: date | None) -> tuple[date, date]:
    """Par défaut : du 1er du mois courant à aujourd'hui. 422 si début > fin."""
    aujourd_hui = date.today()
    debut = date_debut or aujourd_hui.replace(day=1)
    fin = date_fin or aujourd_hui
    if debut > fin:
        raise DonneesInvalides(f"date_debut ({debut}) ne peut pas être postérieure à date_fin ({fin}).")
    return debut, fin


def _somme(expression) -> object:
    return func.coalesce(func.sum(expression), 0)


def chiffre_affaires_entre(db: Session, debut: date, fin: date) -> int:
    return db.scalar(
        select(_somme(Commande.montant_total)).where(
            NON_ANNULEE, Commande.date_commande.between(debut, fin)
        )
    )


def encaisse_entre(db: Session, debut: date, fin: date) -> int:
    return db.scalar(select(_somme(Paiement.montant)).where(Paiement.date_paiement.between(debut, fin)))


# --- Route 39 ----------------------------------------------------------------------------


def tableau_de_bord(db: Session) -> TableauDeBord:
    aujourd_hui = date.today()
    debut_mois = aujourd_hui.replace(day=1)
    fin_mois = (debut_mois.replace(year=debut_mois.year + 1, month=1) if debut_mois.month == 12
                else debut_mois.replace(month=debut_mois.month + 1))
    dans_le_mois = Commande.date_commande >= debut_mois, Commande.date_commande < fin_mois

    par_statut = {statut: 0 for statut in StatutCommande}  # tous les statuts, même à 0
    for statut, nombre in db.execute(select(Commande.statut, func.count()).group_by(Commande.statut)):
        par_statut[statut] = nombre

    pretes = db.scalars(
        select(Commande)
        .options(joinedload(Commande.client))
        .where(Commande.statut == StatutCommande.terminee)
        .order_by(Commande.date_livraison_prevue, Commande.id)
    ).all()

    return TableauDeBord(
        mois=debut_mois.strftime("%Y-%m"),
        chiffre_affaires_mois=db.scalar(
            select(_somme(Commande.montant_total)).where(NON_ANNULEE, *dans_le_mois)
        ),
        encaisse_mois=db.scalar(
            select(_somme(Paiement.montant)).where(
                Paiement.date_paiement >= debut_mois, Paiement.date_paiement < fin_mois
            )
        ),
        nb_commandes_mois=db.scalar(select(func.count()).select_from(Commande).where(NON_ANNULEE, *dans_le_mois)),
        reste_a_encaisser=db.scalar(
            select(_somme(Commande.montant_total - Commande.montant_paye)).where(NON_ANNULEE)
        ),
        commandes_par_statut=par_statut,
        nb_commandes_en_retard=db.scalar(
            select(func.count()).select_from(Commande).where(service_commandes.condition_en_retard())
        ),
        commandes_pretes_a_livrer=[service_commandes.vers_liste(c) for c in pretes],
        livraisons_du_jour=service_livraisons.tournee(
            db, statut=None, date_min=aujourd_hui, date_max=aujourd_hui
        ),
    )


# --- Route 40 ----------------------------------------------------------------------------


def chiffre_affaires(
    db: Session, granularite: Granularite, date_debut: date | None, date_fin: date | None
) -> ChiffreAffaires:
    debut, fin = periode_par_defaut(date_debut, date_fin)
    format_ = "YYYY-MM-DD" if granularite == Granularite.jour else "YYYY-MM"

    periode_cmd = func.to_char(Commande.date_commande, format_)
    ca = dict(db.execute(
        select(periode_cmd, func.sum(Commande.montant_total))
        .where(NON_ANNULEE, Commande.date_commande.between(debut, fin))
        .group_by(periode_cmd)
    ).all())

    periode_pai = func.to_char(Paiement.date_paiement, format_)
    encaisse = dict(db.execute(
        select(periode_pai, func.sum(Paiement.montant))
        .where(Paiement.date_paiement.between(debut, fin))
        .group_by(periode_pai)
    ).all())

    # Seules les périodes avec activité (une commande ou un paiement) sont listées.
    periodes = [
        PeriodeChiffreAffaires(periode=p, chiffre_affaires=ca.get(p, 0), encaisse=encaisse.get(p, 0))
        for p in sorted(set(ca) | set(encaisse))
    ]
    return ChiffreAffaires(
        granularite=granularite,
        date_debut=debut,
        date_fin=fin,
        total_chiffre_affaires=sum(p.chiffre_affaires for p in periodes),
        total_encaisse=sum(p.encaisse for p in periodes),
        periodes=periodes,
    )


# --- Route 41 ----------------------------------------------------------------------------


def par_type_vetement(db: Session, date_debut: date | None, date_fin: date | None) -> list[StatTypeVetement]:
    debut, fin = periode_par_defaut(date_debut, date_fin)
    quantite = func.sum(LigneCommande.quantite)
    montant = func.sum(LigneCommande.quantite * LigneCommande.prix_unitaire)  # avant remise
    lignes = db.execute(
        select(TypeVetement.id, TypeVetement.nom, quantite, montant)
        .join(LigneCommande, LigneCommande.type_vetement_id == TypeVetement.id)
        .join(Commande, Commande.id == LigneCommande.commande_id)
        .where(NON_ANNULEE, Commande.date_commande.between(debut, fin))
        .group_by(TypeVetement.id, TypeVetement.nom)
        .order_by(montant.desc(), quantite.desc(), TypeVetement.nom)
    ).all()
    return [
        StatTypeVetement(type_vetement_id=i, nom=nom, quantite_vendue=q, chiffre_affaires=m)
        for i, nom, q, m in lignes
    ]


# --- Route 42 ----------------------------------------------------------------------------


def top_clients(
    db: Session, date_debut: date | None, date_fin: date | None, limite: int
) -> list[TopClient]:
    debut, fin = periode_par_defaut(date_debut, date_fin)
    ca = func.sum(Commande.montant_total)
    lignes = db.execute(
        select(
            Client.id, Client.prenom, Client.nom, Client.telephone,
            func.count(Commande.id), ca, func.sum(Commande.montant_total - Commande.montant_paye),
        )
        .join(Commande, Commande.client_id == Client.id)
        .where(NON_ANNULEE, Commande.date_commande.between(debut, fin))
        .group_by(Client.id)
        .order_by(ca.desc(), func.count(Commande.id).desc(), Client.nom, Client.prenom)
        .limit(limite)
    ).all()
    return [
        TopClient(client_id=i, client_nom=f"{prenom} {nom}", telephone=tel,
                  nb_commandes=nb, chiffre_affaires=montant, solde_du=solde)
        for i, prenom, nom, tel, nb, montant, solde in lignes
    ]


# --- Route 43 ----------------------------------------------------------------------------


def impayes(db: Session, *, limit: int, offset: int) -> tuple[list[CommandeListe], int]:
    """Commandes non annulées non soldées, les plus urgentes d'abord (date prévue la plus proche)."""
    conditions = (NON_ANNULEE, Commande.montant_total > Commande.montant_paye)
    total = db.scalar(select(func.count()).select_from(Commande).where(*conditions)) or 0
    commandes = db.scalars(
        select(Commande)
        .options(joinedload(Commande.client))
        .where(*conditions)
        .order_by(Commande.date_livraison_prevue, Commande.id)
        .limit(limit)
        .offset(offset)
    ).all()
    return [service_commandes.vers_liste(c) for c in commandes], total
