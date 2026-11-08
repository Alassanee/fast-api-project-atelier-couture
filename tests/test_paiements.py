"""Paiements : routes 32 à 34, RG16, RG17 et droits par rôle."""

from datetime import date, timedelta

import pytest

API = "/api/v1"
AUJOURD_HUI = date.today()


@pytest.fixture
def commande(client, h_accueil, catalogue, fatou):
    """Commande de 75 000 FCFA (2 boubous + 1 pantalon à 10 000 − 5 000 de remise)."""
    r = client.post(f"{API}/commandes", json={
        "client_id": fatou.id,
        "lignes": [
            {"type_vetement_id": catalogue["boubou"].id, "quantite": 2},
            {"type_vetement_id": catalogue["pantalon"].id, "prix_unitaire": 10_000},
        ],
        "remise": 5_000,
    }, headers=h_accueil)
    assert r.status_code == 201
    return r.json()


def payer(client, h, commande_id, montant, mode="wave", **kw):
    return client.post(f"{API}/commandes/{commande_id}/paiements",
                       json={"montant": montant, "mode": mode, **kw}, headers=h)


def detail(client, h, commande_id):
    return client.get(f"{API}/commandes/{commande_id}", headers=h).json()


# --- Route 32 ----------------------------------------------------------------------------

def test_scenario_demo_etape_6_acompte_wave(client, h_accueil, accueil, commande):
    r = payer(client, h_accueil, commande["id"], 30_000, reference="WAVE-123")
    assert r.status_code == 201
    p = r.json()
    assert p["montant"] == 30_000 and p["mode"] == "wave" and p["reference"] == "WAVE-123"
    assert p["date_paiement"] == AUJOURD_HUI.isoformat()  # aujourd'hui par défaut
    assert p["enregistre_par_id"] == accueil.id
    assert p["solde_restant"] == 45_000

    c = detail(client, h_accueil, commande["id"])
    assert c["montant_paye"] == 30_000 and c["solde"] == 45_000
    assert [x["id"] for x in c["paiements"]] == [p["id"]]


def test_scenario_demo_etape_6_paiement_superieur_au_solde_409(client, h_accueil, commande):
    payer(client, h_accueil, commande["id"], 30_000)
    r = payer(client, h_accueil, commande["id"], 45_001)
    assert r.status_code == 409
    assert "45000" in r.json()["detail"].replace(" ", "")  # le solde restant est indiqué
    assert detail(client, h_accueil, commande["id"])["montant_paye"] == 30_000


def test_payer_exactement_le_solde(client, h_accueil, commande):
    payer(client, h_accueil, commande["id"], 30_000)
    r = payer(client, h_accueil, commande["id"], 45_000, mode="especes")
    assert r.status_code == 201 and r.json()["solde_restant"] == 0
    # Commande soldée : plus rien ne peut être encaissé.
    assert payer(client, h_accueil, commande["id"], 1).status_code == 409


@pytest.mark.parametrize("mode", ["especes", "wave", "orange_money", "virement", "cheque"])
def test_tous_les_modes_de_paiement(client, h_accueil, commande, mode):
    assert payer(client, h_accueil, commande["id"], 1_000, mode=mode).status_code == 201


@pytest.mark.parametrize("montant", [0, -500])
def test_rg16_montant_strictement_positif_422(client, h_accueil, commande, montant):
    assert payer(client, h_accueil, commande["id"], montant).status_code == 422


def test_mode_invalide_422(client, h_accueil, commande):
    assert payer(client, h_accueil, commande["id"], 1_000, mode="carte_bleue").status_code == 422


def test_rg16_date_future_422(client, h_accueil, commande):
    demain = (AUJOURD_HUI + timedelta(days=1)).isoformat()
    r = payer(client, h_accueil, commande["id"], 1_000, date_paiement=demain)
    assert r.status_code == 422
    assert "futur" in r.json()["detail"]


def test_date_passee_acceptee(client, h_accueil, commande):
    hier = (AUJOURD_HUI - timedelta(days=1)).isoformat()
    r = payer(client, h_accueil, commande["id"], 1_000, date_paiement=hier)
    assert r.status_code == 201 and r.json()["date_paiement"] == hier


def test_rg16_commande_annulee_409(client, h_accueil, commande):
    client.post(f"{API}/commandes/{commande['id']}/statut", json={"statut": "annulee"}, headers=h_accueil)
    r = payer(client, h_accueil, commande["id"], 1_000)
    assert r.status_code == 409
    assert "annulée" in r.json()["detail"]


def test_commande_inconnue_404(client, h_accueil):
    assert payer(client, h_accueil, 99999, 1_000).status_code == 404
    assert client.get(f"{API}/commandes/99999/paiements", headers=h_accueil).status_code == 404


def test_rg14_avec_un_vrai_acompte_annuler_exige_un_commentaire(client, h_accueil, commande):
    payer(client, h_accueil, commande["id"], 10_000)
    url = f"{API}/commandes/{commande['id']}/statut"
    assert client.post(url, json={"statut": "annulee"}, headers=h_accueil).status_code == 422
    r = client.post(url, json={"statut": "annulee", "commentaire": "Avoir de 10 000"}, headers=h_accueil)
    assert r.status_code == 200


def test_rg7_apres_paiement_la_remise_ne_peut_plus_ramener_le_total_sous_le_paye(
    client, h_accueil, commande
):
    payer(client, h_accueil, commande["id"], 70_000)
    r = client.patch(f"{API}/commandes/{commande['id']}", json={"remise": 15_000}, headers=h_accueil)
    assert r.status_code == 409  # total 65 000 < 70 000 payés


# --- Route 33 ----------------------------------------------------------------------------

def test_liste_dans_l_ordre_de_saisie(client, h_accueil, h_tailleur, commande):
    hier = (AUJOURD_HUI - timedelta(days=1)).isoformat()
    a = payer(client, h_accueil, commande["id"], 10_000).json()
    b = payer(client, h_accueil, commande["id"], 5_000, date_paiement=hier).json()  # saisi après
    liste = client.get(f"{API}/commandes/{commande['id']}/paiements", headers=h_tailleur).json()
    assert [p["id"] for p in liste] == [a["id"], b["id"]]


# --- Route 34 et RG17 -------------------------------------------------------------------------

def test_rg17_annuler_un_paiement_recalcule_le_solde(client, h_accueil, h_admin, commande):
    a = payer(client, h_accueil, commande["id"], 30_000).json()
    payer(client, h_accueil, commande["id"], 20_000)
    assert client.delete(f"{API}/paiements/{a['id']}", headers=h_admin).status_code == 204

    c = detail(client, h_accueil, commande["id"])
    assert c["montant_paye"] == 20_000 and c["solde"] == 55_000
    assert len(c["paiements"]) == 1
    # Le solde libéré peut de nouveau être encaissé.
    assert payer(client, h_accueil, commande["id"], 55_000).status_code == 201


def test_annuler_paiement_inconnu_404(client, h_admin):
    assert client.delete(f"{API}/paiements/99999", headers=h_admin).status_code == 404


# --- Droits ----------------------------------------------------------------------------------

def test_droits_le_tailleur_n_encaisse_pas(client, h_tailleur, commande):
    assert payer(client, h_tailleur, commande["id"], 1_000).status_code == 403


def test_droits_l_admin_encaisse(client, h_admin, commande):
    assert payer(client, h_admin, commande["id"], 1_000).status_code == 201


@pytest.mark.parametrize("role", ["accueil", "tailleur"])
def test_droits_seul_l_admin_annule_un_paiement(client, request, h_accueil, commande, role):
    p = payer(client, h_accueil, commande["id"], 1_000).json()
    h = request.getfixturevalue(f"h_{role}")
    assert client.delete(f"{API}/paiements/{p['id']}", headers=h).status_code == 403


def test_droits_sans_jeton_401(client, commande):
    assert client.get(f"{API}/commandes/{commande['id']}/paiements").status_code == 401
    assert client.post(f"{API}/commandes/{commande['id']}/paiements",
                       json={"montant": 1, "mode": "wave"}).status_code == 401
