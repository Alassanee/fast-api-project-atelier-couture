"""Catalogue des prestations : routes 14 à 17 et droits."""

from datetime import date

import pytest

from app.models import Client, Commande, LigneCommande, TypeVetement
from app.seed import CATALOGUE_DEPART, creer_catalogue

URL = "/api/v1/catalogue"


def boubou(**kw):
    return {"nom": "Boubou", "description": "Bazin brodé", "prix_base": 35_000, "delai_jours": 10, **kw}


def creer(client, h, **kw):
    r = client.post(URL, json=boubou(**kw), headers=h)
    assert r.status_code == 201, r.json()
    return r.json()


def test_creer_prestation(client, h_admin):
    corps = creer(client, h_admin)
    assert corps["nom"] == "Boubou"
    assert corps["prix_base"] == 35_000 and corps["delai_jours"] == 10
    assert corps["actif"] is True


def test_nom_en_double_409(client, h_admin):
    creer(client, h_admin)
    assert client.post(URL, json=boubou(nom="  boubou "), headers=h_admin).status_code == 409


@pytest.mark.parametrize("champ, valeur", [
    ("prix_base", 0), ("prix_base", -500), ("delai_jours", -1), ("nom", "   "), ("prix_base", "cher"),
])
def test_donnees_invalides_422(client, h_admin, champ, valeur):
    assert client.post(URL, json=boubou(**{champ: valeur}), headers=h_admin).status_code == 422


def test_liste_triee_par_nom_et_actives_seulement(client, h_admin, h_tailleur):
    creer(client, h_admin, nom="Robe")
    creer(client, h_admin, nom="Chemise")
    retiree = creer(client, h_admin, nom="Ancienne tenue")
    client.patch(f"{URL}/{retiree['id']}", json={"actif": False}, headers=h_admin)

    actives = [p["nom"] for p in client.get(URL, headers=h_tailleur).json()]
    assert actives == ["Chemise", "Robe"]

    toutes = client.get(URL, params={"actifs_seulement": "false"}, headers=h_tailleur).json()
    assert [p["nom"] for p in toutes] == ["Ancienne tenue", "Chemise", "Robe"]


def test_detail_et_404(client, h_admin, h_accueil):
    p = creer(client, h_admin)
    assert client.get(f"{URL}/{p['id']}", headers=h_accueil).json()["nom"] == "Boubou"
    assert client.get(f"{URL}/99999", headers=h_accueil).status_code == 404


def test_patch_prix_delai_nom(client, h_admin):
    p = creer(client, h_admin)
    r = client.patch(f"{URL}/{p['id']}", json={"prix_base": 40_000, "delai_jours": 12}, headers=h_admin)
    assert r.status_code == 200
    assert r.json()["prix_base"] == 40_000 and r.json()["delai_jours"] == 12
    assert r.json()["nom"] == "Boubou"
    r = client.patch(f"{URL}/{p['id']}", json={"nom": "Grand boubou"}, headers=h_admin)
    assert r.json()["nom"] == "Grand boubou"


def test_patch_garder_son_nom_n_est_pas_un_doublon(client, h_admin):
    p = creer(client, h_admin)
    assert client.patch(f"{URL}/{p['id']}", json={"nom": "Boubou"}, headers=h_admin).status_code == 200


def test_patch_nom_d_une_autre_prestation_409(client, h_admin):
    creer(client, h_admin)
    robe = creer(client, h_admin, nom="Robe")
    assert client.patch(f"{URL}/{robe['id']}", json={"nom": "Boubou"}, headers=h_admin).status_code == 409


@pytest.mark.parametrize("corps", [{"nom": ""}, {"prix_base": None}, {"actif": None}, {"prix_base": 0}])
def test_patch_invalide_422(client, h_admin, corps):
    p = creer(client, h_admin)
    assert client.patch(f"{URL}/{p['id']}", json=corps, headers=h_admin).status_code == 422


def test_patch_404(client, h_admin):
    assert client.patch(f"{URL}/99999", json={"prix_base": 1000}, headers=h_admin).status_code == 404


def test_retrait_et_changement_de_prix_ne_touchent_pas_les_anciennes_commandes(
    client, db, h_admin, accueil
):
    p = creer(client, h_admin)
    cli = Client(nom="Diop", prenom="Fatou", telephone="771234567")
    db.add(cli)
    db.flush()
    commande = Commande(
        numero="CMD-2026-00001", client_id=cli.id, date_commande=date.today(),
        date_livraison_prevue=date.today(), montant_total=70_000, cree_par_id=accueil.id,
    )
    commande.lignes.append(LigneCommande(type_vetement_id=p["id"], quantite=2, prix_unitaire=35_000))
    db.add(commande)
    db.commit()

    client.patch(f"{URL}/{p['id']}", json={"prix_base": 50_000, "actif": False}, headers=h_admin)

    db.expire_all()
    ligne = db.query(LigneCommande).one()
    assert ligne.prix_unitaire == 35_000
    assert ligne.type_vetement_id == p["id"]
    assert db.get(Commande, commande.id).montant_total == 70_000


def test_seed_cree_le_catalogue_de_l_annexe_b(db):
    creer_catalogue(db)
    db.commit()
    creer_catalogue(db)  # relancé : pas de doublon
    db.commit()
    prestations = {p.nom: (p.prix_base, p.delai_jours) for p in db.query(TypeVetement).all()}
    assert prestations == {nom: (prix, delai) for nom, _, prix, delai in CATALOGUE_DEPART}
    assert prestations["Boubou"] == (35_000, 10)
    assert prestations["Retouche"] == (3_000, 2)


@pytest.mark.parametrize("role", ["accueil", "tailleur"])
def test_droits_seul_l_admin_modifie_le_catalogue(client, request, h_admin, role):
    p = creer(client, h_admin)
    h = request.getfixturevalue(f"h_{role}")
    assert client.post(URL, json=boubou(nom="Robe"), headers=h).status_code == 403
    assert client.patch(f"{URL}/{p['id']}", json={"prix_base": 1}, headers=h).status_code == 403
    # Lecture autorisée à tout utilisateur connecté
    assert client.get(URL, headers=h).status_code == 200
    assert client.get(f"{URL}/{p['id']}", headers=h).status_code == 200


def test_droits_sans_jeton_401(client):
    assert client.get(URL).status_code == 401
