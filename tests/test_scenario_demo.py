"""Annexe A : le scénario de démonstration complet, de bout en bout.

Tout passe par l'API HTTP, comme dans Swagger le jour de la démonstration :
chaque acteur se connecte avec son e-mail et son mot de passe.
"""

import re
from datetime import date, timedelta

from app.seed import creer_catalogue
from tests.conftest import MOT_DE_PASSE

API = "/api/v1"


def connexion(client, email, mot_de_passe):
    r = client.post(f"{API}/auth/login", data={"username": email, "password": mot_de_passe})
    assert r.status_code == 200, r.json()
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_scenario_de_demonstration_annexe_a(client, db, admin):
    # --- Préparation : catalogue de l'annexe B et comptes du personnel -----------------
    creer_catalogue(db)
    db.commit()
    h_admin = connexion(client, admin.email, MOT_DE_PASSE)
    for email, nom, role in [("accueil@atelier.sn", "Aïssatou Ndiaye", "accueil"),
                             ("tailleur@atelier.sn", "Moussa Diallo", "tailleur")]:
        r = client.post(f"{API}/utilisateurs", json={"email": email, "nom_complet": nom,
                                                     "mot_de_passe": "secret-demo", "role": role},
                        headers=h_admin)
        assert r.status_code == 201
    catalogue = {p["nom"]: p for p in client.get(f"{API}/catalogue", headers=h_admin).json()}
    ca_mois_avant = client.get(f"{API}/statistiques/tableau-de-bord", headers=h_admin).json()[
        "chiffre_affaires_mois"]

    # --- Étape 1 : l'accueil crée Fatou Diop ; le doublon est refusé ------------------------
    h_accueil = connexion(client, "accueil@atelier.sn", "secret-demo")
    r = client.post(f"{API}/clients", json={"nom": "Diop", "prenom": "Fatou", "telephone": "77 123 45 67",
                                            "genre": "femme"}, headers=h_accueil)
    assert r.status_code == 201
    fatou = r.json()
    assert fatou["telephone"] == "771234567"
    r = client.post(f"{API}/clients", json={"nom": "Autre", "prenom": "Client", "telephone": "771234567"},
                    headers=h_accueil)
    assert r.status_code == 409

    # --- Étape 2 : le tailleur prend les mesures ; l'accueil reçoit 403 -----------------------
    h_tailleur = connexion(client, "tailleur@atelier.sn", "secret-demo")
    mesures = {"tour_cou": 36, "tour_poitrine": 92, "tour_taille": 74, "longueur_robe": 140}
    r = client.post(f"{API}/clients/{fatou['id']}/mesures", json=mesures, headers=h_tailleur)
    assert r.status_code == 201
    mesure = r.json()
    r = client.post(f"{API}/clients/{fatou['id']}/mesures", json=mesures, headers=h_accueil)
    assert r.status_code == 403

    # --- Étape 3 : 2 boubous et 1 pantalon à prix négocié, avec une remise --------------------
    r = client.post(f"{API}/commandes", json={
        "client_id": fatou["id"],
        "lignes": [
            {"type_vetement_id": catalogue["Boubou"]["id"], "quantite": 2},
            {"type_vetement_id": catalogue["Pantalon"]["id"], "quantite": 1, "prix_unitaire": 10_000},
        ],
        "remise": 5_000,
    }, headers=h_accueil)
    assert r.status_code == 201
    commande = r.json()
    cid = commande["id"]
    assert re.fullmatch(rf"CMD-{date.today().year}-\d{{5}}", commande["numero"])
    assert commande["montant_total"] == 2 * 35_000 + 10_000 - 5_000 == 75_000
    assert commande["date_livraison_prevue"] == (date.today() + timedelta(days=10)).isoformat()
    assert commande["mesure_id"] == mesure["id"]
    assert commande["statut"] == "en_attente"

    # --- Étape 4 : passage direct à « terminee » refusé, statuts possibles indiqués -----------
    r = client.post(f"{API}/commandes/{cid}/statut", json={"statut": "terminee"}, headers=h_accueil)
    assert r.status_code == 409
    assert "Statuts possibles : annulee, en_coupe" in r.json()["detail"]

    # --- Étape 5 : production jusqu'à « terminee », avec essayage / retouches ----------------
    for statut in ["en_coupe", "en_couture", "essayage", "retouches", "essayage", "terminee"]:
        r = client.post(f"{API}/commandes/{cid}/statut", json={"statut": statut}, headers=h_tailleur)
        assert r.status_code == 200, r.json()
    historique = client.get(f"{API}/commandes/{cid}/historique", headers=h_accueil).json()
    assert [h["nouveau_statut"] for h in historique] == [
        "en_attente", "en_coupe", "en_couture", "essayage", "retouches", "essayage", "terminee",
    ]
    assert historique[0]["ancien_statut"] is None

    # --- Étape 6 : acompte Wave ; paiement supérieur au solde refusé ------------------------
    r = client.post(f"{API}/commandes/{cid}/paiements",
                    json={"montant": 30_000, "mode": "wave", "reference": "WV-0001"}, headers=h_accueil)
    assert r.status_code == 201 and r.json()["solde_restant"] == 45_000
    r = client.post(f"{API}/commandes/{cid}/paiements", json={"montant": 50_000, "mode": "wave"},
                    headers=h_accueil)
    assert r.status_code == 409

    # --- Étape 7 : confirmation refusée, le solde n'est pas payé ------------------------------
    r = client.post(f"{API}/commandes/{cid}/livraison/confirmer", headers=h_accueil)
    assert r.status_code == 409

    # --- Étape 8 : encaissement du solde puis livraison -------------------------------------
    r = client.post(f"{API}/commandes/{cid}/paiements", json={"montant": 45_000, "mode": "especes"},
                    headers=h_accueil)
    assert r.status_code == 201 and r.json()["solde_restant"] == 0
    r = client.post(f"{API}/commandes/{cid}/livraison/confirmer", headers=h_accueil)
    assert r.status_code == 200
    assert r.json()["statut"] == "livree" and r.json()["solde"] == 0

    # --- Étape 9 : tableau de bord de l'admin ; l'accueil reçoit 403 ---------------------------
    tableau = client.get(f"{API}/statistiques/tableau-de-bord", headers=h_admin).json()
    assert tableau["chiffre_affaires_mois"] == ca_mois_avant + 75_000
    assert tableau["commandes_par_statut"]["livree"] == 1
    assert client.get(f"{API}/statistiques/tableau-de-bord", headers=h_accueil).status_code == 403

    # --- Étape 10 : impayés et commandes en retard --------------------------------------------
    impayes = client.get(f"{API}/statistiques/impayes", headers=h_admin)
    assert impayes.status_code == 200
    assert cid not in [c["id"] for c in impayes.json()["items"]]  # soldée : plus dans les impayés
    retards = client.get(f"{API}/commandes", params={"en_retard": "true"}, headers=h_admin)
    assert retards.status_code == 200
    assert cid not in [c["id"] for c in retards.json()["items"]]  # livrée : jamais en retard
