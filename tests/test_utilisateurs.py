"""Gestion des comptes : routes 3 à 6, droits par rôle et RG24."""

import pytest

from app.enums import Role
from tests.conftest import MOT_DE_PASSE

URL = "/api/v1/utilisateurs"


def nouveau(**kw):
    return {"email": "fatou@atelier.sn", "nom_complet": "Fatou Sow",
            "mot_de_passe": "secret123", "role": "tailleur", **kw}


def test_creer_utilisateur(client, h_admin):
    r = client.post(URL, json=nouveau(), headers=h_admin)
    assert r.status_code == 201
    corps = r.json()
    assert corps["email"] == "fatou@atelier.sn"
    assert corps["role"] == "tailleur"
    assert corps["actif"] is True
    assert "mot_de_passe_hash" not in corps and "mot_de_passe" not in corps


def test_le_nouveau_compte_peut_se_connecter(client, h_admin):
    client.post(URL, json=nouveau(), headers=h_admin)
    r = client.post("/api/v1/auth/login", data={"username": "fatou@atelier.sn", "password": "secret123"})
    assert r.status_code == 200


def test_email_en_double_409(client, h_admin):
    assert client.post(URL, json=nouveau(), headers=h_admin).status_code == 201
    r = client.post(URL, json=nouveau(email="FATOU@atelier.sn"), headers=h_admin)
    assert r.status_code == 409


def test_rg21_mot_de_passe_trop_court_422(client, h_admin):
    r = client.post(URL, json=nouveau(mot_de_passe="court"), headers=h_admin)
    assert r.status_code == 422


def test_role_invalide_422(client, h_admin):
    assert client.post(URL, json=nouveau(role="patron"), headers=h_admin).status_code == 422


def test_lister_tries_par_nom(client, h_admin, creer_utilisateur):
    creer_utilisateur(Role.tailleur, nom_complet="Zeynab Ba")
    creer_utilisateur(Role.accueil, nom_complet="Binta Fall")
    noms = [u["nom_complet"] for u in client.get(URL, headers=h_admin).json()]
    assert noms == sorted(noms)
    assert len(noms) == 3


def test_obtenir_et_404(client, h_admin, admin):
    assert client.get(f"{URL}/{admin.id}", headers=h_admin).status_code == 200
    assert client.get(f"{URL}/99999", headers=h_admin).status_code == 404


def test_modifier_partiellement(client, h_admin, tailleur):
    r = client.patch(f"{URL}/{tailleur.id}", json={"nom_complet": "Moussa Ndiaye"}, headers=h_admin)
    assert r.status_code == 200
    assert r.json()["nom_complet"] == "Moussa Ndiaye"
    assert r.json()["role"] == "tailleur"  # champ non envoyé : inchangé


def test_modifier_mot_de_passe(client, h_admin, tailleur):
    client.patch(f"{URL}/{tailleur.id}", json={"mot_de_passe": "nouveau123"}, headers=h_admin)
    login = lambda p: client.post("/api/v1/auth/login", data={"username": tailleur.email, "password": p})
    assert login(MOT_DE_PASSE).status_code == 401
    assert login("nouveau123").status_code == 200


def test_desactiver_un_compte_bloque_la_connexion(client, h_admin, tailleur):
    client.patch(f"{URL}/{tailleur.id}", json={"actif": False}, headers=h_admin)
    r = client.post("/api/v1/auth/login", data={"username": tailleur.email, "password": MOT_DE_PASSE})
    assert r.status_code == 401


def test_champ_obligatoire_a_null_422(client, h_admin, tailleur):
    assert client.patch(f"{URL}/{tailleur.id}", json={"role": None}, headers=h_admin).status_code == 422


def test_rg24_admin_ne_peut_pas_se_desactiver(client, h_admin, admin):
    r = client.patch(f"{URL}/{admin.id}", json={"actif": False}, headers=h_admin)
    assert r.status_code == 409


def test_rg24_admin_ne_peut_pas_retirer_son_role(client, h_admin, admin):
    r = client.patch(f"{URL}/{admin.id}", json={"role": "accueil"}, headers=h_admin)
    assert r.status_code == 409


def test_rg24_admin_peut_desactiver_un_autre_admin(client, h_admin, creer_utilisateur):
    autre = creer_utilisateur(Role.admin)
    r = client.patch(f"{URL}/{autre.id}", json={"actif": False}, headers=h_admin)
    assert r.status_code == 200


@pytest.mark.parametrize("role", ["accueil", "tailleur"])
def test_droits_seul_l_admin_gere_les_comptes(client, role, request, admin):
    h = request.getfixturevalue(f"h_{role}")
    assert client.get(URL, headers=h).status_code == 403
    assert client.get(f"{URL}/{admin.id}", headers=h).status_code == 403
    assert client.post(URL, json=nouveau(), headers=h).status_code == 403
    assert client.patch(f"{URL}/{admin.id}", json={"nom_complet": "X"}, headers=h).status_code == 403


def test_droits_sans_jeton_401(client):
    assert client.get(URL).status_code == 401
