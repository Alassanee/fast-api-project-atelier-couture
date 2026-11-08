"""Mesures : routes 18 à 23, RG2, RG3, RG4 et droits par rôle."""

from datetime import date, timedelta

import pytest

from app.models import Commande
from app.models.mesure import CHAMPS_MESURES

API = "/api/v1"


def url_client(client_id):
    return f"{API}/clients/{client_id}/mesures"


def prendre(client, h, client_id, **valeurs):
    corps = valeurs or {"tour_poitrine": 92, "tour_taille": 74.5, "longueur_robe": 120}
    r = client.post(url_client(client_id), json=corps, headers=h)
    assert r.status_code == 201, r.json()
    return r.json()


# --- Route 18 et RG2 -----------------------------------------------------------

def test_scenario_demo_le_tailleur_prend_les_mesures(client, h_tailleur, tailleur, fatou):
    m = prendre(client, h_tailleur, fatou.id)
    assert m["client_id"] == fatou.id
    assert m["prise_par_id"] == tailleur.id  # le tailleur connecté
    assert m["date_prise"] == date.today().isoformat()  # aujourd'hui par défaut
    assert m["tour_taille"] == 74.5
    assert m["tour_cou"] is None  # mesures facultatives
    assert set(CHAMPS_MESURES) <= set(m)


def test_scenario_demo_l_accueil_recoit_403(client, h_accueil, fatou):
    r = client.post(url_client(fatou.id), json={"tour_cou": 38}, headers=h_accueil)
    assert r.status_code == 403


def test_l_admin_peut_prendre_des_mesures(client, h_admin, fatou):
    prendre(client, h_admin, fatou.id, tour_cou=38)


def test_date_prise_fournie(client, h_tailleur, fatou):
    m = prendre(client, h_tailleur, fatou.id, tour_cou=38, date_prise="2026-01-15", notes="Pagne")
    assert m["date_prise"] == "2026-01-15" and m["notes"] == "Pagne"


def test_rg2_au_moins_une_mesure_422(client, h_tailleur, fatou):
    r = client.post(url_client(fatou.id), json={"notes": "rien"}, headers=h_tailleur)
    assert r.status_code == 422
    assert "au moins une mesure" in r.json()["detail"]
    assert client.post(url_client(fatou.id), json={"tour_cou": None}, headers=h_tailleur).status_code == 422


@pytest.mark.parametrize("valeur", [0, -5, 300.1, 450])
def test_rg2_mesure_hors_limites_422(client, h_tailleur, fatou, valeur):
    r = client.post(url_client(fatou.id), json={"tour_cou": valeur}, headers=h_tailleur)
    assert r.status_code == 422


def test_rg2_bornes_acceptees(client, h_tailleur, fatou):
    prendre(client, h_tailleur, fatou.id, taille_cm=300, tour_poignet=0.5)


def test_client_inconnu_404(client, h_tailleur):
    assert client.post(url_client(99999), json={"tour_cou": 38}, headers=h_tailleur).status_code == 404


# --- Routes 19 à 21 et RG3 -------------------------------------------------------

def test_rg3_historique_conserve_plus_recente_d_abord(client, h_tailleur, h_accueil, fatou):
    ancienne = prendre(client, h_tailleur, fatou.id, tour_cou=36, date_prise="2025-06-01")
    recente = prendre(client, h_tailleur, fatou.id, tour_cou=38, date_prise="2026-03-01")
    # Saisie après coup d'une prise plus ancienne : elle ne devient pas « la dernière ».
    rattrapage = prendre(client, h_tailleur, fatou.id, tour_cou=37, date_prise="2025-12-01")

    hist = client.get(url_client(fatou.id), headers=h_accueil).json()
    assert [m["id"] for m in hist] == [recente["id"], rattrapage["id"], ancienne["id"]]

    derniere = client.get(f"{url_client(fatou.id)}/derniere", headers=h_accueil).json()
    assert derniere["id"] == recente["id"]


def test_derniere_404_si_aucune_mesure(client, h_accueil, fatou):
    r = client.get(f"{url_client(fatou.id)}/derniere", headers=h_accueil)
    assert r.status_code == 404


def test_historique_client_inconnu_404(client, h_accueil):
    assert client.get(url_client(99999), headers=h_accueil).status_code == 404
    assert client.get(f"{url_client(99999)}/derniere", headers=h_accueil).status_code == 404


def test_obtenir_une_prise_et_404(client, h_tailleur, h_accueil, fatou):
    m = prendre(client, h_tailleur, fatou.id)
    assert client.get(f"{API}/mesures/{m['id']}", headers=h_accueil).json()["id"] == m["id"]
    assert client.get(f"{API}/mesures/99999", headers=h_accueil).status_code == 404


# --- Route 22 : correction ---------------------------------------------------------

def test_corriger_une_mesure(client, h_tailleur, fatou):
    m = prendre(client, h_tailleur, fatou.id)
    r = client.patch(f"{API}/mesures/{m['id']}", json={"tour_taille": 76, "tour_poitrine": None},
                     headers=h_tailleur)
    assert r.status_code == 200
    assert r.json()["tour_taille"] == 76
    assert r.json()["tour_poitrine"] is None
    assert r.json()["longueur_robe"] == 120  # non envoyé : inchangé


def test_rg2_correction_qui_supprime_toutes_les_mesures_422(client, h_tailleur, fatou):
    m = prendre(client, h_tailleur, fatou.id, tour_cou=38)
    r = client.patch(f"{API}/mesures/{m['id']}", json={"tour_cou": None}, headers=h_tailleur)
    assert r.status_code == 422
    # Rien n'a été enregistré
    assert client.get(f"{API}/mesures/{m['id']}", headers=h_tailleur).json()["tour_cou"] == 38


@pytest.mark.parametrize("corps", [{"tour_cou": 0}, {"tour_cou": 301}, {"date_prise": None}])
def test_correction_invalide_422(client, h_tailleur, fatou, corps):
    m = prendre(client, h_tailleur, fatou.id)
    assert client.patch(f"{API}/mesures/{m['id']}", json=corps, headers=h_tailleur).status_code == 422


def test_correction_404(client, h_tailleur):
    assert client.patch(f"{API}/mesures/99999", json={"tour_cou": 38}, headers=h_tailleur).status_code == 404


# --- Route 23 et RG4 -------------------------------------------------------------------

def test_supprimer_une_prise(client, h_tailleur, fatou):
    m = prendre(client, h_tailleur, fatou.id)
    assert client.delete(f"{API}/mesures/{m['id']}", headers=h_tailleur).status_code == 204
    assert client.get(f"{API}/mesures/{m['id']}", headers=h_tailleur).status_code == 404


def test_rg4_mesures_utilisees_par_une_commande_409(client, db, h_tailleur, accueil, fatou):
    m = prendre(client, h_tailleur, fatou.id)
    db.add(Commande(
        numero="CMD-2026-00001", client_id=fatou.id, mesure_id=m["id"], date_commande=date.today(),
        date_livraison_prevue=date.today() + timedelta(days=7), cree_par_id=accueil.id,
    ))
    db.commit()
    r = client.delete(f"{API}/mesures/{m['id']}", headers=h_tailleur)
    assert r.status_code == 409
    assert "commande" in r.json()["detail"]


def test_supprimer_404(client, h_tailleur):
    assert client.delete(f"{API}/mesures/99999", headers=h_tailleur).status_code == 404


# --- Droits --------------------------------------------------------------------------

def test_droits_l_accueil_ne_corrige_ni_ne_supprime(client, h_tailleur, h_accueil, fatou):
    m = prendre(client, h_tailleur, fatou.id)
    assert client.patch(f"{API}/mesures/{m['id']}", json={"tour_cou": 40}, headers=h_accueil).status_code == 403
    assert client.delete(f"{API}/mesures/{m['id']}", headers=h_accueil).status_code == 403


@pytest.mark.parametrize("role", ["admin", "accueil", "tailleur"])
def test_droits_tout_utilisateur_connecte_consulte(client, request, h_tailleur, fatou, role):
    m = prendre(client, h_tailleur, fatou.id)
    h = request.getfixturevalue(f"h_{role}")
    assert client.get(url_client(fatou.id), headers=h).status_code == 200
    assert client.get(f"{url_client(fatou.id)}/derniere", headers=h).status_code == 200
    assert client.get(f"{API}/mesures/{m['id']}", headers=h).status_code == 200


def test_droits_sans_jeton_401(client, fatou):
    assert client.get(url_client(fatou.id)).status_code == 401
    assert client.post(url_client(fatou.id), json={"tour_cou": 38}).status_code == 401
