"""Logique métier des livraisons (RG18, RG19, RG20 ; routes 35 à 38)."""

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.enums import ModeLivraison, StatutCommande, StatutLivraison
from app.exceptions import Conflit, DonneesInvalides, NonTrouve
from app.models import Client, Commande, Livraison, Utilisateur
from app.schemas.livraison import ConfirmationLivraison, LivraisonPlanification, LivraisonTournee
from app.services import commandes as service_commandes


def planifier(db: Session, commande_id: int, donnees: LivraisonPlanification) -> Livraison:
    commande = service_commandes.obtenir(db, commande_id)
    service_commandes.verifier_modifiable(commande)  # livrée ou annulée : 409

    adresse = (donnees.adresse or "").strip() or None
    # RG18 : une livraison à domicile exige une adresse.
    if donnees.mode == ModeLivraison.domicile and not adresse:
        raise DonneesInvalides("Une livraison à domicile exige une adresse.")
    if donnees.date_prevue < commande.date_commande:
        raise DonneesInvalides(
            f"La date de livraison prévue ({donnees.date_prevue}) ne peut pas précéder "
            f"la date de commande ({commande.date_commande})."
        )

    # RG18 : replanifier modifie la livraison existante, sans en créer une seconde.
    livraison = commande.livraison or Livraison(commande=commande, statut=StatutLivraison.planifiee)
    livraison.mode = donnees.mode
    livraison.date_prevue = donnees.date_prevue
    livraison.adresse = adresse
    livraison.livreur = (donnees.livreur or "").strip() or None
    livraison.notes = donnees.notes
    # RG18 : planifier met à jour la date de livraison prévue de la commande.
    commande.date_livraison_prevue = donnees.date_prevue
    db.add(livraison)
    db.flush()
    return livraison


def obtenir(db: Session, commande_id: int) -> Livraison:
    commande = service_commandes.obtenir(db, commande_id)
    if commande.livraison is None:
        raise NonTrouve(f"Aucune livraison n'est planifiée pour la commande {commande.numero}.")
    return commande.livraison


def confirmer(
    db: Session, commande_id: int, donnees: ConfirmationLivraison, acteur: Utilisateur
) -> Commande:
    commande = service_commandes.obtenir(db, commande_id)

    # RG19 : la commande doit être « terminee »…
    if commande.statut != StatutCommande.terminee:
        raise Conflit(
            f"Livraison impossible : la commande est « {commande.statut.value} », "
            "elle doit être « terminee »."
        )
    # … et soldée, sauf autorisation explicite.
    if commande.solde > 0 and not donnees.autoriser_solde_impaye:
        raise Conflit(
            f"Livraison refusée : il reste {commande.solde} FCFA impayés sur la commande "
            f"{commande.numero}. Encaissez le solde ou envoyez autoriser_solde_impaye à true."
        )

    date_effective = donnees.date_effective or date.today()
    if date_effective > date.today():
        raise DonneesInvalides(f"La date de livraison effective ({date_effective}) ne peut pas être future.")
    if date_effective < commande.date_commande:
        raise DonneesInvalides(
            f"La date de livraison effective ({date_effective}) ne peut pas précéder "
            f"la date de commande ({commande.date_commande})."
        )

    # RG20 : sans planification préalable, un retrait à l'atelier est créé.
    livraison = commande.livraison
    if livraison is None:
        livraison = Livraison(
            commande=commande, mode=ModeLivraison.retrait_atelier,
            date_prevue=commande.date_livraison_prevue,
        )
        db.add(livraison)
    livraison.statut = StatutLivraison.livree
    livraison.date_effective = date_effective

    # RG20 : la commande passe à « livree » avec sa date de livraison réelle.
    commande.statut = StatutCommande.livree
    commande.date_livraison_reelle = date_effective
    commentaire = None
    if commande.solde > 0:
        # RG19 : la dette reste visible et la mention est inscrite dans l'historique.
        commentaire = f"Livrée avec un solde impayé de {commande.solde} FCFA (autorisé)."
    service_commandes.historiser(
        commande, StatutCommande.terminee, StatutCommande.livree, acteur, commentaire
    )
    db.flush()
    return commande


def tournee(
    db: Session, *, statut: StatutLivraison | None, date_min: date | None, date_max: date | None
) -> list[LivraisonTournee]:
    """Route 38 : liste de tournée triée par date prévue (commandes annulées exclues)."""
    if date_min and date_max and date_min > date_max:
        raise DonneesInvalides("date_min ne peut pas être postérieure à date_max.")
    requete = (
        select(Livraison)
        .join(Livraison.commande)
        .options(joinedload(Livraison.commande).joinedload(Commande.client))
        .where(Commande.statut != StatutCommande.annulee)
    )
    if statut is not None:
        requete = requete.where(Livraison.statut == statut)
    if date_min is not None:
        requete = requete.where(Livraison.date_prevue >= date_min)
    if date_max is not None:
        requete = requete.where(Livraison.date_prevue <= date_max)

    livraisons = db.scalars(requete.order_by(Livraison.date_prevue, Livraison.id)).all()
    resultat = []
    for livraison in livraisons:
        commande = livraison.commande
        client: Client = commande.client
        resultat.append(
            LivraisonTournee(
                id=livraison.id,
                commande_id=livraison.commande_id,
                mode=livraison.mode,
                adresse=livraison.adresse,
                livreur=livraison.livreur,
                date_prevue=livraison.date_prevue,
                date_effective=livraison.date_effective,
                statut=livraison.statut,
                notes=livraison.notes,
                numero_commande=commande.numero,
                client_nom=f"{client.prenom} {client.nom}",
                client_telephone=client.telephone,
                solde_commande=commande.solde,
            )
        )
    return resultat
