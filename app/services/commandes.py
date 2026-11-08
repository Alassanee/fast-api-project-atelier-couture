"""Logique métier des commandes (routes 24 à 31).

Règles appliquées : RG5 à RG15 et le workflow des statuts (section 6).
"""

from collections.abc import Sequence
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import ColumnElement, Select, and_, func, not_, select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.enums import Role, StatutCommande
from app.exceptions import Conflit, DonneesInvalides, Interdit, NonTrouve
from app.models import Commande, HistoriqueStatut, LigneCommande, Mesure, TypeVetement, Utilisateur
from app.schemas.commande import (
    ChangementStatut,
    CommandeCreate,
    CommandeDetail,
    CommandeListe,
    CommandeUpdate,
    HistoriqueRead,
    LigneCreate,
    LigneRead,
)
from app.schemas.livraison import LivraisonRead
from app.schemas.paiement import PaiementRead
from app.services import clients as service_clients
from app.services import mesures as service_mesures

S = StatutCommande
STATUTS_FINAUX = (S.livree, S.annulee)

# Workflow des statuts (section 6). « livree » ne s'obtient que par la
# confirmation de livraison (RG13), jamais par la route de changement de statut.
TRANSITIONS: dict[StatutCommande, tuple[StatutCommande, ...]] = {
    S.en_attente: (S.en_coupe, S.annulee),
    S.en_coupe: (S.en_couture, S.annulee),
    S.en_couture: (S.essayage, S.terminee, S.annulee),
    S.essayage: (S.retouches, S.terminee, S.annulee),
    S.retouches: (S.essayage, S.terminee, S.annulee),
    S.terminee: (S.livree,),
    S.livree: (),
    S.annulee: (),
}


# --- Calculs et indicateurs ----------------------------------------------------------


def est_en_retard(commande: Commande, aujourd_hui: date | None = None) -> bool:
    """RG11 : date prévue dépassée et commande ni livrée ni annulée."""
    aujourd_hui = aujourd_hui or date.today()
    return commande.date_livraison_prevue < aujourd_hui and commande.statut not in STATUTS_FINAUX


def condition_en_retard(aujourd_hui: date | None = None) -> ColumnElement[bool]:
    """RG11 traduite en condition SQL (filtres et statistiques)."""
    aujourd_hui = aujourd_hui or date.today()
    return and_(
        Commande.date_livraison_prevue < aujourd_hui,
        Commande.statut.not_in(STATUTS_FINAUX),
    )


def recalculer_montants(commande: Commande) -> None:
    """RG7 : total = Σ(quantité × prix unitaire) − remise ; payé = Σ paiements.

    La remise ne peut pas dépasser la somme des prestations (422) et le total
    ne peut jamais passer sous le montant déjà payé (409).
    """
    somme_prestations = sum(ligne.quantite * ligne.prix_unitaire for ligne in commande.lignes)
    if commande.remise > somme_prestations:
        raise DonneesInvalides(
            f"La remise ({commande.remise} FCFA) dépasse la somme des prestations "
            f"({somme_prestations} FCFA)."
        )
    montant_paye = sum(p.montant for p in commande.paiements)
    total = somme_prestations - commande.remise
    if total < montant_paye:
        raise Conflit(
            f"Modification refusée : le nouveau total ({total} FCFA) serait inférieur "
            f"au montant déjà payé ({montant_paye} FCFA)."
        )
    commande.montant_total = total
    commande.montant_paye = montant_paye


def _numero(commande: Commande) -> str:
    """RG5 : CMD-AAAA-NNNNN (année de commande, puis identifiant sur 5 chiffres)."""
    return f"CMD-{commande.date_commande.year}-{commande.id:05d}"


# --- Conversions vers les schémas de réponse --------------------------------------------


def nom_client(commande: Commande) -> str:
    return f"{commande.client.prenom} {commande.client.nom}"


def vers_liste(commande: Commande) -> CommandeListe:
    return CommandeListe(
        id=commande.id,
        numero=commande.numero,
        client_id=commande.client_id,
        client_nom=nom_client(commande),
        statut=commande.statut,
        date_commande=commande.date_commande,
        date_livraison_prevue=commande.date_livraison_prevue,
        montant_total=commande.montant_total,
        montant_paye=commande.montant_paye,
        solde=commande.solde,
        en_retard=est_en_retard(commande),
    )


def vers_detail(commande: Commande) -> CommandeDetail:
    return CommandeDetail(
        id=commande.id,
        numero=commande.numero,
        client_id=commande.client_id,
        client_nom=nom_client(commande),
        mesure_id=commande.mesure_id,
        statut=commande.statut,
        date_commande=commande.date_commande,
        date_livraison_prevue=commande.date_livraison_prevue,
        date_livraison_reelle=commande.date_livraison_reelle,
        remise=commande.remise,
        montant_total=commande.montant_total,
        montant_paye=commande.montant_paye,
        solde=commande.solde,
        en_retard=est_en_retard(commande),
        notes=commande.notes,
        cree_par_id=commande.cree_par_id,
        created_at=commande.created_at,
        updated_at=commande.updated_at,
        lignes=[
            LigneRead(
                id=ligne.id,
                type_vetement_id=ligne.type_vetement_id,
                type_vetement_nom=ligne.type_vetement.nom,
                description=ligne.description,
                quantite=ligne.quantite,
                prix_unitaire=ligne.prix_unitaire,
                sous_total=ligne.sous_total,
            )
            for ligne in commande.lignes
        ],
        paiements=[PaiementRead.model_validate(p) for p in commande.paiements],
        livraison=LivraisonRead.model_validate(commande.livraison) if commande.livraison else None,
    )


# --- Lecture ---------------------------------------------------------------------------


def _avec_details(requete: Select) -> Select:
    return requete.options(
        joinedload(Commande.client),
        selectinload(Commande.lignes).joinedload(LigneCommande.type_vetement),
        selectinload(Commande.paiements),
        selectinload(Commande.livraison),
    )


def obtenir(db: Session, commande_id: int) -> Commande:
    commande = db.scalar(_avec_details(select(Commande).where(Commande.id == commande_id)))
    if commande is None:
        raise NonTrouve(f"Commande {commande_id} introuvable.")
    return commande


def lister(
    db: Session,
    *,
    statut: StatutCommande | None = None,
    client_id: int | None = None,
    en_retard: bool | None = None,
    date_min: date | None = None,
    date_max: date | None = None,
    numero: str | None = None,
    limit: int,
    offset: int,
) -> tuple[list[CommandeListe], int]:
    if date_min and date_max and date_min > date_max:
        raise DonneesInvalides("date_min ne peut pas être postérieure à date_max.")
    conditions: list[ColumnElement[bool]] = []
    if statut is not None:
        conditions.append(Commande.statut == statut)
    if client_id is not None:
        conditions.append(Commande.client_id == client_id)
    if en_retard is not None:
        conditions.append(condition_en_retard() if en_retard else not_(condition_en_retard()))
    if date_min is not None:
        conditions.append(Commande.date_commande >= date_min)
    if date_max is not None:
        conditions.append(Commande.date_commande <= date_max)
    if numero:
        conditions.append(Commande.numero.ilike(f"%{numero.strip()}%"))

    total = db.scalar(select(func.count()).select_from(Commande).where(*conditions)) or 0
    commandes = db.scalars(
        select(Commande)
        .options(joinedload(Commande.client))
        .where(*conditions)
        .order_by(Commande.date_commande.desc(), Commande.id.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    return [vers_liste(c) for c in commandes], total


def historique(db: Session, commande_id: int) -> list[HistoriqueRead]:
    obtenir(db, commande_id)
    lignes: Sequence[HistoriqueStatut] = db.scalars(
        select(HistoriqueStatut)
        .options(joinedload(HistoriqueStatut.utilisateur))
        .where(HistoriqueStatut.commande_id == commande_id)
        .order_by(HistoriqueStatut.date_changement, HistoriqueStatut.id)
    ).all()
    return [
        HistoriqueRead(
            id=h.id,
            commande_id=h.commande_id,
            ancien_statut=h.ancien_statut,
            nouveau_statut=h.nouveau_statut,
            commentaire=h.commentaire,
            utilisateur_id=h.utilisateur_id,
            utilisateur_nom=h.utilisateur.nom_complet,
            date_changement=h.date_changement,
        )
        for h in lignes
    ]


# --- Contrôles communs -------------------------------------------------------------------


def verifier_modifiable(commande: Commande) -> None:
    """RG12 : une commande livrée ou annulée n'est plus modifiable."""
    if commande.statut in STATUTS_FINAUX:
        raise Conflit(
            f"La commande {commande.numero} est « {commande.statut.value} » : "
            "elle n'est plus modifiable."
        )


def _verifier_lignes_modifiables(commande: Commande) -> None:
    """RG10 : les lignes ne sont modifiables que tant que la commande est en attente."""
    verifier_modifiable(commande)
    if commande.statut != S.en_attente:
        raise Conflit(
            f"Les lignes ne sont modifiables que pour une commande « en_attente » "
            f"(statut actuel : {commande.statut.value})."
        )


def _mesure_du_client(db: Session, mesure_id: int, client_id: int) -> Mesure:
    """RG9 : les mesures rattachées doivent appartenir au client de la commande."""
    mesure = db.get(Mesure, mesure_id)
    if mesure is None:
        raise NonTrouve(f"Prise de mesures {mesure_id} introuvable.")
    if mesure.client_id != client_id:
        raise DonneesInvalides(
            f"Les mesures {mesure_id} n'appartiennent pas au client de la commande."
        )
    return mesure


def _nouvelle_ligne(db: Session, donnees: LigneCreate) -> LigneCommande:
    """RG6 : prix par défaut = prix de base ; prestation inactive refusée (422)."""
    prestation = db.get(TypeVetement, donnees.type_vetement_id)
    if prestation is None:
        raise NonTrouve(f"Prestation {donnees.type_vetement_id} introuvable dans le catalogue.")
    if not prestation.actif:
        raise DonneesInvalides(
            f"La prestation « {prestation.nom} » n'est plus proposée : elle ne peut pas être commandée."
        )
    return LigneCommande(
        type_vetement=prestation,
        description=donnees.description,
        quantite=donnees.quantite,
        prix_unitaire=donnees.prix_unitaire if donnees.prix_unitaire is not None else prestation.prix_base,
    )


def _verifier_date_prevue(commande: Commande, date_prevue: date) -> None:
    """RG8 : la date de livraison prévue ne peut pas précéder la date de commande."""
    if date_prevue < commande.date_commande:
        raise DonneesInvalides(
            f"La date de livraison prévue ({date_prevue}) ne peut pas précéder "
            f"la date de commande ({commande.date_commande})."
        )


def historiser(
    commande: Commande, ancien: StatutCommande | None, nouveau: StatutCommande,
    auteur: Utilisateur, commentaire: str | None = None,
) -> None:
    """RG15 : chaque changement de statut est inscrit dans l'historique."""
    commande.historique.append(
        HistoriqueStatut(
            ancien_statut=ancien,
            nouveau_statut=nouveau,
            commentaire=commentaire,
            utilisateur_id=auteur.id,
            date_changement=datetime.now(UTC),
        )
    )


# --- Écriture ----------------------------------------------------------------------------


def creer(db: Session, donnees: CommandeCreate, auteur: Utilisateur) -> Commande:
    client = service_clients.obtenir(db, donnees.client_id)

    # RG9 : mesures du client, ou à défaut ses dernières mesures s'il en a.
    if donnees.mesure_id is not None:
        mesure = _mesure_du_client(db, donnees.mesure_id, client.id)
    else:
        mesure = service_mesures.dernieres(db, client.id)

    commande = Commande(
        client=client,
        mesure=mesure,
        statut=S.en_attente,
        date_commande=date.today(),
        remise=donnees.remise,
        montant_paye=0,
        notes=donnees.notes,
        cree_par_id=auteur.id,
    )
    commande.lignes = [_nouvelle_ligne(db, ligne) for ligne in donnees.lignes]

    # RG8 : date prévue par défaut = date de commande + plus long délai commandé.
    if donnees.date_livraison_prevue is not None:
        _verifier_date_prevue(commande, donnees.date_livraison_prevue)
        commande.date_livraison_prevue = donnees.date_livraison_prevue
    else:
        delai = max(ligne.type_vetement.delai_jours for ligne in commande.lignes)
        commande.date_livraison_prevue = commande.date_commande + timedelta(days=delai)

    recalculer_montants(commande)  # RG7
    historiser(commande, None, S.en_attente, auteur)  # RG15 : première ligne
    db.add(commande)
    db.flush()
    commande.numero = _numero(commande)  # RG5 : l'identifiant est connu après insertion
    db.flush()
    return commande


def modifier(db: Session, commande_id: int, donnees: CommandeUpdate) -> Commande:
    commande = obtenir(db, commande_id)
    verifier_modifiable(commande)  # RG12
    changements = donnees.model_dump(exclude_unset=True)

    if "mesure_id" in changements:
        mesure_id = changements["mesure_id"]
        commande.mesure = _mesure_du_client(db, mesure_id, commande.client_id) if mesure_id else None
    if "date_livraison_prevue" in changements:
        _verifier_date_prevue(commande, changements["date_livraison_prevue"])
        commande.date_livraison_prevue = changements["date_livraison_prevue"]
    if "remise" in changements:
        commande.remise = changements["remise"]
    if "notes" in changements:
        commande.notes = changements["notes"]

    recalculer_montants(commande)  # RG7
    db.flush()
    return commande


def _message_transition(actuel: StatutCommande, demande: StatutCommande) -> str:
    possibles = TRANSITIONS[actuel]
    if not possibles:
        suite = "aucun (statut final)"
    elif possibles == (S.livree,):
        suite = "livree (uniquement par la confirmation de livraison)"
    else:
        suite = ", ".join(sorted(s.value for s in possibles))
    return f"Transition interdite : {actuel.value} → {demande.value}. Statuts possibles : {suite}"


def changer_statut(
    db: Session, commande_id: int, donnees: ChangementStatut, acteur: Utilisateur
) -> Commande:
    commande = obtenir(db, commande_id)
    actuel, demande = commande.statut, donnees.statut
    commentaire = (donnees.commentaire or "").strip() or None

    # RG14 : le tailleur ne peut pas annuler une commande.
    if demande == S.annulee and acteur.role == Role.tailleur:
        raise Interdit("Le tailleur ne peut pas annuler une commande.")
    # RG13 : demander le statut déjà en cours est refusé.
    if demande == actuel:
        raise Conflit(f"La commande est déjà au statut « {actuel.value} ».")
    # RG13 : « livree » résulte uniquement de la confirmation de livraison.
    if demande == S.livree:
        raise Conflit(
            "Le statut « livree » ne peut pas être posé ici : il résulte de la "
            "confirmation de livraison (POST /commandes/{id}/livraison/confirmer)."
        )
    # Workflow (section 6) ; couvre aussi RG12 pour les statuts finaux.
    if demande not in TRANSITIONS[actuel]:
        raise Conflit(_message_transition(actuel, demande))
    # RG14 : annuler une commande avec acompte exige d'expliquer le sort de l'argent.
    if demande == S.annulee and commande.montant_paye > 0 and not commentaire:
        raise DonneesInvalides(
            f"Cette commande a reçu {commande.montant_paye} FCFA : un commentaire expliquant "
            "le sort de l'argent (remboursement, avoir...) est obligatoire pour l'annuler."
        )

    commande.statut = demande
    historiser(commande, actuel, demande, acteur, commentaire)  # RG15
    db.flush()
    return commande


def ajouter_ligne(db: Session, commande_id: int, donnees: LigneCreate) -> Commande:
    commande = obtenir(db, commande_id)
    _verifier_lignes_modifiables(commande)  # RG10, RG12
    commande.lignes.append(_nouvelle_ligne(db, donnees))
    recalculer_montants(commande)
    db.flush()
    return commande


def supprimer_ligne(db: Session, commande_id: int, ligne_id: int) -> Commande:
    commande = obtenir(db, commande_id)
    ligne = next((lg for lg in commande.lignes if lg.id == ligne_id), None)
    if ligne is None:
        raise NonTrouve(f"Ligne {ligne_id} introuvable dans la commande {commande.numero}.")
    _verifier_lignes_modifiables(commande)  # RG10, RG12
    if len(commande.lignes) == 1:
        raise Conflit("Une commande doit toujours garder au moins une ligne.")
    commande.lignes.remove(ligne)
    recalculer_montants(commande)
    db.flush()
    return commande
