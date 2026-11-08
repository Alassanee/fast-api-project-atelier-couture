"""Livraisons : routes 35 à 38, RG18, RG19, RG20 et droits par rôle."""

from datetime import date, timedelta

import pytest

API = "/api/v1"
AUJOURD_HUI = date.today()
DANS_5_JOURS = (AUJOURD_HUI + timedelta(days=5)).isoformat()


def url(commande_id, suffixe=""):
    return f"{API}/commandes/{commande_id}/livraison{suffixe}"


def planifier(client, h, commande_id, **kw):
    corps = {"mode": "domicile", "date_prevue": DANS_5_JOURS, "adresse": "Sicap Liberté 2, Dakar",
             "livreur": "Modou", **kw}
    return client.put(url(commande_id), json=corps, headers=h)


def terminer(client, h_tailleur, commande_id):
    for statut in ("en_coupe", "en_couture", "terminee"):
        r = client.post(f"{API}/commandes/{commande_id}/statut", json={"statut": statut}, headers=h_tailleur)
        assert r.status_code == 200, r.json()


def payer(client, h, commande_id, montant, mode="wave"):
    r = client.post(f"{API}/commandes/{commande_id}/paiements", json={"montant": montant, "mode": mode},
                    headers=h)
    assert r.status_code == 201, r.json()


def confirmer(client, h, commande_id, corps=None):
    return client.post(url(commande_id, "/confirmer"), json=corps, headers=h)


# --- Route 35 : planification (RG18) -------------------------------------------------------

def test_planifier_une_livraison_a_domicile(client, h_accueil, commande):
    r = planifier(client, h_accueil, commande["id"])
    assert r.status_code == 200
    liv = r.json()
    assert liv["mode"] == "domicile" and liv["statut"] == "planifiee"
    assert liv["adresse"] == "Sicap Liberté 2, Dakar" and liv["livreur"] == "Modou"
    assert liv["date_effective"] is None


def test_rg18_planifier_met_a_jour_la_date_prevue_de_la_commande(client, h_accueil, commande):
    planifier(client, h_accueil, commande["id"])
    c = client.get(f"{API}/commandes/{commande['id']}", headers=h_accueil).json()
    assert c["date_livraison_prevue"] == DANS_5_JOURS
    assert c["livraison"]["date_prevue"] == DANS_5_JOURS


@pytest.mark.parametrize("adresse", [None, "", "   "])
def test_rg18_domicile_sans_adresse_422(client, h_accueil, commande, adresse):
    r = planifier(client, h_accueil, commande["id"], adresse=adresse)
    assert r.status_code == 422
    assert "adresse" in r.json()["detail"]


def test_retrait_atelier_sans_adresse(client, h_accueil, commande):
    r = planifier(client, h_accueil, commande["id"], mode="retrait_atelier", adresse=None)
    assert r.status_code == 200 and r.json()["adresse"] is None


def test_rg18_replanifier_modifie_la_livraison_existante(client, h_accueil, commande):
    premiere = planifier(client, h_accueil, commande["id"]).json()
    nouvelle_date = (AUJOURD_HUI + timedelta(days=8)).isoformat()
    seconde = planifier(client, h_accueil, commande["id"], mode="retrait_atelier",
                        date_prevue=nouvelle_date, adresse=None).json()
    assert seconde["id"] == premiere["id"]  # pas de seconde livraison
    assert seconde["mode"] == "retrait_atelier" and seconde["date_prevue"] == nouvelle_date
    assert len(client.get(f"{API}/livraisons", headers=h_accueil).json()) == 1


def test_date_prevue_avant_la_commande_422(client, h_accueil, commande):
    hier = (AUJOURD_HUI - timedelta(days=1)).isoformat()
    assert planifier(client, h_accueil, commande["id"], date_prevue=hier).status_code == 422


@pytest.mark.parametrize("corps", [{"mode": "drone"}, {"date_prevue": None}])
def test_planification_invalide_422(client, h_accueil, commande, corps):
    assert planifier(client, h_accueil, commande["id"], **corps).status_code == 422


def test_planifier_commande_annulee_409(client, h_accueil, commande):
    client.post(f"{API}/commandes/{commande['id']}/statut", json={"statut": "annulee"}, headers=h_accueil)
    assert planifier(client, h_accueil, commande["id"]).status_code == 409


def test_planifier_commande_livree_409(client, h_accueil, h_tailleur, commande):
    terminer(client, h_tailleur, commande["id"])
    payer(client, h_accueil, commande["id"], 75_000)
    assert confirmer(client, h_accueil, commande["id"]).status_code == 200
    assert planifier(client, h_accueil, commande["id"]).status_code == 409


def test_planifier_commande_inconnue_404(client, h_accueil):
    assert planifier(client, h_accueil, 99999).status_code == 404


# --- Route 36 -------------------------------------------------------------------------------

def test_lire_la_livraison_et_404(client, h_accueil, h_tailleur, commande):
    assert client.get(url(commande["id"]), headers=h_tailleur).status_code == 404  # pas planifiée
    planifier(client, h_accueil, commande["id"])
    assert client.get(url(commande["id"]), headers=h_tailleur).json()["mode"] == "domicile"
    assert client.get(url(99999), headers=h_tailleur).status_code == 404


# --- Route 37 : confirmation (RG19, RG20) -----------------------------------------------------

def test_rg19_commande_non_terminee_409(client, h_accueil, commande):
    payer(client, h_accueil, commande["id"], 75_000)
    r = confirmer(client, h_accueil, commande["id"])
    assert r.status_code == 409
    assert "terminee" in r.json()["detail"]


def test_scenario_demo_etape_7_solde_impaye_409(client, h_accueil, h_tailleur, commande):
    terminer(client, h_tailleur, commande["id"])
    payer(client, h_accueil, commande["id"], 30_000)  # acompte Wave
    r = confirmer(client, h_accueil, commande["id"])
    assert r.status_code == 409
    assert "45000" in r.json()["detail"].replace(" ", "")  # le montant impayé est indiqué
    assert client.get(f"{API}/commandes/{commande['id']}", headers=h_accueil).json()["statut"] == "terminee"


def test_scenario_demo_etape_8_solde_puis_livraison(client, h_accueil, h_tailleur, accueil, commande):
    terminer(client, h_tailleur, commande["id"])
    payer(client, h_accueil, commande["id"], 30_000)
    payer(client, h_accueil, commande["id"], 45_000, mode="especes")  # le solde
    planifier(client, h_accueil, commande["id"])

    r = confirmer(client, h_accueil, commande["id"])
    assert r.status_code == 200
    c = r.json()
    assert c["statut"] == "livree" and c["solde"] == 0
    # RG20 : dates renseignées
    assert c["date_livraison_reelle"] == AUJOURD_HUI.isoformat()
    assert c["livraison"]["statut"] == "livree"
    assert c["livraison"]["date_effective"] == AUJOURD_HUI.isoformat()
    assert c["livraison"]["mode"] == "domicile"  # la livraison planifiée est conservée

    hist = client.get(f"{API}/commandes/{commande['id']}/historique", headers=h_accueil).json()
    assert (hist[-1]["ancien_statut"], hist[-1]["nouveau_statut"]) == ("terminee", "livree")
    assert hist[-1]["utilisateur_id"] == accueil.id


def test_rg20_sans_planification_un_retrait_atelier_est_cree(client, h_accueil, h_tailleur, commande):
    terminer(client, h_tailleur, commande["id"])
    payer(client, h_accueil, commande["id"], 75_000)
    c = confirmer(client, h_accueil, commande["id"]).json()
    assert c["livraison"]["mode"] == "retrait_atelier"
    assert c["livraison"]["statut"] == "livree"
    assert client.get(url(commande["id"]), headers=h_accueil).status_code == 200


def test_rg19_autoriser_solde_impaye(client, h_accueil, h_tailleur, commande):
    terminer(client, h_tailleur, commande["id"])
    payer(client, h_accueil, commande["id"], 30_000)
    r = confirmer(client, h_accueil, commande["id"], {"autoriser_solde_impaye": True})
    assert r.status_code == 200
    c = r.json()
    assert c["statut"] == "livree"
    assert c["solde"] == 45_000  # la dette reste visible
    hist = client.get(f"{API}/commandes/{commande['id']}/historique", headers=h_accueil).json()
    assert "45000" in hist[-1]["commentaire"].replace(" ", "")
    assert "impayé" in hist[-1]["commentaire"]


def test_date_effective_fournie(client, h_accueil, h_tailleur, commande):
    terminer(client, h_tailleur, commande["id"])
    payer(client, h_accueil, commande["id"], 75_000)
    c = confirmer(client, h_accueil, commande["id"], {"date_effective": AUJOURD_HUI.isoformat()}).json()
    assert c["livraison"]["date_effective"] == AUJOURD_HUI.isoformat()


def test_date_effective_future_422(client, h_accueil, h_tailleur, commande):
    terminer(client, h_tailleur, commande["id"])
    payer(client, h_accueil, commande["id"], 75_000)
    demain = (AUJOURD_HUI + timedelta(days=1)).isoformat()
    assert confirmer(client, h_accueil, commande["id"], {"date_effective": demain}).status_code == 422


def test_confirmer_deux_fois_409(client, h_accueil, h_tailleur, commande):
    terminer(client, h_tailleur, commande["id"])
    payer(client, h_accueil, commande["id"], 75_000)
    assert confirmer(client, h_accueil, commande["id"]).status_code == 200
    assert confirmer(client, h_accueil, commande["id"]).status_code == 409


def test_une_commande_livree_n_est_plus_modifiable(client, h_accueil, h_tailleur, commande):
    terminer(client, h_tailleur, commande["id"])
    payer(client, h_accueil, commande["id"], 75_000)
    confirmer(client, h_accueil, commande["id"])
    assert client.patch(f"{API}/commandes/{commande['id']}", json={"notes": "x"},
                        headers=h_accueil).status_code == 409  # RG12


def test_confirmer_commande_inconnue_404(client, h_accueil):
    assert confirmer(client, h_accueil, 99999).status_code == 404


# --- Route 38 : tournée ------------------------------------------------------------------------

def test_liste_de_tournee(client, db, h_accueil, h_tailleur, catalogue, fatou, commande):
    from app.models import Client

    ibou = Client(nom="Ba", prenom="Ibou", telephone="780000000")
    db.add(ibou)
    db.commit()
    autre = client.post(f"{API}/commandes", json={
        "client_id": ibou.id, "lignes": [{"type_vetement_id": catalogue["retouche"].id}],
    }, headers=h_accueil).json()
    annulee = client.post(f"{API}/commandes", json={
        "client_id": ibou.id, "lignes": [{"type_vetement_id": catalogue["retouche"].id}],
    }, headers=h_accueil).json()

    planifier(client, h_accueil, commande["id"], date_prevue=(AUJOURD_HUI + timedelta(days=9)).isoformat())
    planifier(client, h_accueil, autre["id"], mode="retrait_atelier", adresse=None,
              date_prevue=(AUJOURD_HUI + timedelta(days=2)).isoformat())
    planifier(client, h_accueil, annulee["id"], date_prevue=(AUJOURD_HUI + timedelta(days=1)).isoformat())
    client.post(f"{API}/commandes/{annulee['id']}/statut", json={"statut": "annulee"}, headers=h_accueil)

    liste = client.get(f"{API}/livraisons", headers=h_tailleur).json()
    assert [l["commande_id"] for l in liste] == [autre["id"], commande["id"]]  # par date prévue
    premiere = liste[0]
    assert premiere["numero_commande"] == autre["numero"]
    assert premiere["client_nom"] == "Ibou Ba"
    assert premiere["client_telephone"] == "780000000"
    assert premiere["solde_commande"] == 3_000

    filtre = lambda **p: [l["commande_id"] for l in client.get(f"{API}/livraisons", params=p,
                                                                headers=h_tailleur).json()]
    assert filtre(statut="planifiee") == [autre["id"], commande["id"]]
    assert filtre(statut="livree") == []
    assert filtre(date_min=(AUJOURD_HUI + timedelta(days=3)).isoformat()) == [commande["id"]]
    assert filtre(date_max=(AUJOURD_HUI + timedelta(days=3)).isoformat()) == [autre["id"]]
    assert client.get(f"{API}/livraisons", params={"date_min": "2026-02-01", "date_max": "2026-01-01"},
                      headers=h_tailleur).status_code == 422


# --- Droits ------------------------------------------------------------------------------------

def test_droits_le_tailleur_ne_planifie_ni_ne_confirme(client, h_accueil, h_tailleur, commande):
    assert planifier(client, h_tailleur, commande["id"]).status_code == 403
    terminer(client, h_tailleur, commande["id"])
    payer(client, h_accueil, commande["id"], 75_000)
    assert confirmer(client, h_tailleur, commande["id"]).status_code == 403


def test_droits_l_admin_planifie_et_confirme(client, h_admin, h_accueil, h_tailleur, commande):
    assert planifier(client, h_admin, commande["id"]).status_code == 200
    terminer(client, h_tailleur, commande["id"])
    payer(client, h_accueil, commande["id"], 75_000)
    assert confirmer(client, h_admin, commande["id"]).status_code == 200


def test_droits_sans_jeton_401(client, commande):
    assert client.get(f"{API}/livraisons").status_code == 401
    assert client.get(url(commande["id"])).status_code == 401
