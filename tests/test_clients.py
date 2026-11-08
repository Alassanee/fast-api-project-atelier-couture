"""Clients : routes 7 à 13, RG1 (téléphone), RG4 (suppression) et droits."""

from datetime import date, timedelta

import pytest

from app.enums import StatutCommande
from app.models import Commande, Mesure

URL = "/api/v1/clients"


def fatou(**kw):
    return {"nom": "Diop", "prenom": "Fatou", "telephone": "77 123 45 67", "genre": "femme", **kw}


def creer(client, h, **kw):
    r = client.post(URL, json=fatou(**kw), headers=h)
    assert r.status_code == 201, r.json()
    return r.json()


def ajouter_commande(db, client_id, auteur_id, *, statut=StatutCommande.en_attente,
                     total=50_000, paye=0, jours=0, prevue_dans=10):
    c = Commande(
        client_id=client_id, statut=statut, date_commande=date.today() - timedelta(days=jours),
        date_livraison_prevue=date.today() + timedelta(days=prevue_dans),
        montant_total=total, montant_paye=paye, cree_par_id=auteur_id,
    )
    db.add(c)
    db.flush()
    c.numero = f"CMD-{c.date_commande.year}-{c.id:05d}"
    db.commit()
    return c


# --- RG1 : téléphone ------------------------------------------------------------

def test_creer_client_normalise_le_telephone(client, h_accueil):
    corps = creer(client, h_accueil)
    assert corps["telephone"] == "771234567"
    assert corps["nom"] == "Diop" and corps["prenom"] == "Fatou"


def test_rg1_scenario_demo_doublon_409(client, h_accueil):
    creer(client, h_accueil)
    r = client.post(URL, json=fatou(nom="Ndiaye", telephone="771234567"), headers=h_accueil)
    assert r.status_code == 409
    assert "téléphone" in r.json()["detail"]


@pytest.mark.parametrize("tel", ["(77) 123-45.67", "+221 77 123 45 67", "123456"])
def test_rg1_formats_acceptes(client, h_accueil, tel):
    assert client.post(URL, json=fatou(telephone=tel), headers=h_accueil).status_code == 201


@pytest.mark.parametrize("tel", ["12345", "77A1234567", "77+1234567", "1" * 21, "++771234567"])
def test_rg1_numero_invalide_422(client, h_accueil, tel):
    r = client.post(URL, json=fatou(telephone=tel), headers=h_accueil)
    assert r.status_code == 422
    assert isinstance(r.json()["detail"], str)


def test_champs_obligatoires_422(client, h_accueil):
    assert client.post(URL, json={"nom": "Diop"}, headers=h_accueil).status_code == 422
    assert client.post(URL, json=fatou(nom="   "), headers=h_accueil).status_code == 422
    assert client.post(URL, json=fatou(genre="autre"), headers=h_accueil).status_code == 422


# --- Liste, recherche, pagination -------------------------------------------------

@pytest.fixture
def plusieurs_clients(client, h_accueil):
    for nom, prenom, tel, genre in [
        ("Sow", "Awa", "770000001", "femme"),
        ("Diop", "Moussa", "770000002", "homme"),
        ("Diop", "Aminata", "770000003", "femme"),
        ("Ba", "Ibou", "780000004", "enfant"),
    ]:
        creer(client, h_accueil, nom=nom, prenom=prenom, telephone=tel, genre=genre)


def test_liste_paginee_triee_par_nom_puis_prenom(client, h_tailleur, plusieurs_clients):
    r = client.get(URL, headers=h_tailleur)
    assert r.status_code == 200
    corps = r.json()
    assert set(corps) == {"items", "total", "limit", "offset"}
    assert corps["total"] == 4 and corps["limit"] == 20 and corps["offset"] == 0
    assert [(c["nom"], c["prenom"]) for c in corps["items"]] == [
        ("Ba", "Ibou"), ("Diop", "Aminata"), ("Diop", "Moussa"), ("Sow", "Awa"),
    ]


def test_pagination_limit_offset(client, h_accueil, plusieurs_clients):
    corps = client.get(URL, params={"limit": 2, "offset": 1}, headers=h_accueil).json()
    assert corps["total"] == 4
    assert [c["prenom"] for c in corps["items"]] == ["Aminata", "Moussa"]
    assert client.get(URL, params={"limit": 101}, headers=h_accueil).status_code == 422


def test_recherche_q(client, h_accueil, plusieurs_clients):
    noms = lambda q: [c["prenom"] for c in client.get(URL, params={"q": q}, headers=h_accueil).json()["items"]]
    assert noms("diop") == ["Aminata", "Moussa"]
    assert noms("awa") == ["Awa"]
    assert noms("78000") == ["Ibou"]
    assert noms("77 000 000 2") == ["Moussa"]
    assert noms("Moussa Diop") == ["Moussa"]


def test_recherche_q_trop_courte_422(client, h_accueil):
    assert client.get(URL, params={"q": "a"}, headers=h_accueil).status_code == 422


def test_filtre_genre(client, h_accueil, plusieurs_clients):
    corps = client.get(URL, params={"genre": "femme"}, headers=h_accueil).json()
    assert corps["total"] == 2


# --- Fiche, modification ------------------------------------------------------------

def test_fiche_et_404(client, h_accueil):
    c = creer(client, h_accueil)
    assert client.get(f"{URL}/{c['id']}", headers=h_accueil).json()["telephone"] == "771234567"
    assert client.get(f"{URL}/99999", headers=h_accueil).status_code == 404


def test_patch_partiel(client, h_accueil):
    c = creer(client, h_accueil, email="fatou@mail.sn")
    r = client.patch(f"{URL}/{c['id']}", json={"adresse": "Médina, Dakar"}, headers=h_accueil)
    assert r.status_code == 200
    assert r.json()["adresse"] == "Médina, Dakar"
    assert r.json()["email"] == "fatou@mail.sn"


def test_patch_garder_son_numero_n_est_pas_un_doublon(client, h_accueil):
    c = creer(client, h_accueil)
    r = client.patch(f"{URL}/{c['id']}", json={"telephone": "77.123.45.67"}, headers=h_accueil)
    assert r.status_code == 200


def test_patch_numero_d_un_autre_client_409(client, h_accueil):
    creer(client, h_accueil)
    autre = creer(client, h_accueil, telephone="780000000")
    r = client.patch(f"{URL}/{autre['id']}", json={"telephone": "77 123 45 67"}, headers=h_accueil)
    assert r.status_code == 409


@pytest.mark.parametrize("champ", ["nom", "prenom", "telephone"])
@pytest.mark.parametrize("valeur", ["", "   ", None])
def test_patch_ne_peut_pas_vider_les_champs_obligatoires(client, h_accueil, champ, valeur):
    c = creer(client, h_accueil)
    assert client.patch(f"{URL}/{c['id']}", json={champ: valeur}, headers=h_accueil).status_code == 422


def test_patch_numero_invalide_422(client, h_accueil):
    c = creer(client, h_accueil)
    assert client.patch(f"{URL}/{c['id']}", json={"telephone": "abc"}, headers=h_accueil).status_code == 422


def test_patch_404(client, h_accueil):
    assert client.patch(f"{URL}/99999", json={"nom": "X"}, headers=h_accueil).status_code == 404


# --- Suppression (RG4) ---------------------------------------------------------------

def test_suppression_par_admin_supprime_aussi_les_mesures(client, db, h_admin, h_accueil, tailleur):
    c = creer(client, h_accueil)
    db.add(Mesure(client_id=c["id"], date_prise=date.today(), prise_par_id=tailleur.id, tour_cou=38))
    db.commit()
    assert client.delete(f"{URL}/{c['id']}", headers=h_admin).status_code == 204
    assert client.get(f"{URL}/{c['id']}", headers=h_admin).status_code == 404
    db.expire_all()
    assert db.query(Mesure).count() == 0


def test_rg4_client_avec_commandes_409(client, db, h_admin, h_accueil, accueil):
    c = creer(client, h_accueil)
    ajouter_commande(db, c["id"], accueil.id)
    r = client.delete(f"{URL}/{c['id']}", headers=h_admin)
    assert r.status_code == 409
    assert client.get(f"{URL}/{c['id']}", headers=h_admin).status_code == 200


def test_suppression_404(client, h_admin):
    assert client.delete(f"{URL}/99999", headers=h_admin).status_code == 404


@pytest.mark.parametrize("role", ["accueil", "tailleur"])
def test_droits_seul_l_admin_supprime(client, request, h_accueil, role):
    c = creer(client, h_accueil)
    h = request.getfixturevalue(f"h_{role}")
    assert client.delete(f"{URL}/{c['id']}", headers=h).status_code == 403


# --- Commandes du client et résumé -------------------------------------------------------

def test_commandes_du_client_plus_recente_d_abord(client, db, h_tailleur, h_accueil, accueil):
    c = creer(client, h_accueil)
    ancienne = ajouter_commande(db, c["id"], accueil.id, jours=5, prevue_dans=-1)
    recente = ajouter_commande(db, c["id"], accueil.id, jours=0, total=30_000, paye=10_000)
    corps = client.get(f"{URL}/{c['id']}/commandes", headers=h_tailleur).json()
    assert corps["total"] == 2
    premier, second = corps["items"]
    assert premier["id"] == recente.id and second["id"] == ancienne.id
    assert premier["client_nom"] == "Fatou Diop"
    assert premier["solde"] == 20_000
    assert premier["en_retard"] is False
    assert second["en_retard"] is True  # RG11 : date prévue dépassée


def test_commandes_client_inconnu_404(client, h_accueil):
    assert client.get(f"{URL}/99999/commandes", headers=h_accueil).status_code == 404


def test_resume_exclut_les_commandes_annulees(client, db, h_accueil, accueil, tailleur):
    c = creer(client, h_accueil)
    vide = client.get(f"{URL}/{c['id']}/resume", headers=h_accueil).json()
    assert vide == {"nb_commandes": 0, "chiffre_affaires": 0, "total_paye": 0, "solde_du": 0,
                    "derniere_commande": None, "a_des_mesures": False}

    ajouter_commande(db, c["id"], accueil.id, total=50_000, paye=20_000, jours=3)
    derniere = ajouter_commande(db, c["id"], accueil.id, total=30_000, paye=30_000, jours=1)
    ajouter_commande(db, c["id"], accueil.id, statut=StatutCommande.annulee, total=99_000)
    db.add(Mesure(client_id=c["id"], date_prise=date.today(), prise_par_id=tailleur.id, tour_cou=38))
    db.commit()

    r = client.get(f"{URL}/{c['id']}/resume", headers=h_accueil).json()
    assert r["nb_commandes"] == 2
    assert r["chiffre_affaires"] == 80_000
    assert r["total_paye"] == 50_000
    assert r["solde_du"] == 30_000
    assert r["derniere_commande"]["id"] == derniere.id
    assert r["a_des_mesures"] is True


# --- Droits ----------------------------------------------------------------------------

@pytest.mark.parametrize("role", ["admin", "accueil", "tailleur"])
def test_droits_tout_utilisateur_connecte_cree_et_consulte(client, request, role):
    h = request.getfixturevalue(f"h_{role}")
    c = creer(client, h)
    assert client.get(URL, headers=h).status_code == 200
    assert client.get(f"{URL}/{c['id']}", headers=h).status_code == 200
    assert client.patch(f"{URL}/{c['id']}", json={"notes": "VIP"}, headers=h).status_code == 200


def test_droits_sans_jeton_401(client):
    assert client.get(URL).status_code == 401
    assert client.post(URL, json=fatou()).status_code == 401
