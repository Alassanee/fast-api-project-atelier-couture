"""Commandes : routes 24 à 31, RG5 à RG15 et workflow des statuts."""

import re
from datetime import date, timedelta

import pytest

from app.enums import ModePaiement
from app.models import Client, Commande, Mesure, Paiement

URL = "/api/v1/commandes"
AUJOURD_HUI = date.today()


# --- Données de départ --------------------------------------------------------------

@pytest.fixture
def mesures_fatou(db, fatou, tailleur):
    ancienne = Mesure(client_id=fatou.id, date_prise=AUJOURD_HUI - timedelta(days=30),
                      prise_par_id=tailleur.id, tour_poitrine=90)
    recente = Mesure(client_id=fatou.id, date_prise=AUJOURD_HUI, prise_par_id=tailleur.id, tour_poitrine=92)
    db.add_all([ancienne, recente])
    db.commit()
    return ancienne, recente


def corps_demo(catalogue, fatou, **kw):
    """Scénario de démo, étape 3 : 2 boubous et 1 pantalon à prix négocié, avec une remise."""
    return {
        "client_id": fatou.id,
        "lignes": [
            {"type_vetement_id": catalogue["boubou"].id, "quantite": 2},
            {"type_vetement_id": catalogue["pantalon"].id, "quantite": 1, "prix_unitaire": 10_000},
        ],
        "remise": 5_000,
        **kw,
    }


def creer(client, h, corps):
    r = client.post(URL, json=corps, headers=h)
    assert r.status_code == 201, r.json()
    return r.json()


def statut(client, h, commande_id, nouveau, commentaire=None):
    return client.post(f"{URL}/{commande_id}/statut", json={"statut": nouveau, "commentaire": commentaire},
                       headers=h)


def payer(db, commande_id, montant, auteur_id):
    """Simule un paiement déjà encaissé (la route paiements arrive à l'étape 10)."""
    db.add(Paiement(commande_id=commande_id, montant=montant, mode=ModePaiement.wave,
                    date_paiement=AUJOURD_HUI, enregistre_par_id=auteur_id))
    commande = db.get(Commande, commande_id)
    commande.montant_paye += montant
    db.commit()


# --- Route 24 : création ----------------------------------------------------------------

def test_scenario_demo_etape_3(client, h_accueil, accueil, catalogue, fatou, mesures_fatou):
    c = creer(client, h_accueil, corps_demo(catalogue, fatou))
    # RG5 : numéro CMD-AAAA-NNNNN
    assert re.fullmatch(rf"CMD-{AUJOURD_HUI.year}-\d{{5}}", c["numero"])
    assert c["numero"] == f"CMD-{AUJOURD_HUI.year}-{c['id']:05d}"
    # RG6 / RG7 : 2 × 35 000 + 1 × 10 000 − 5 000
    assert c["montant_total"] == 75_000
    assert c["montant_paye"] == 0 and c["solde"] == 75_000
    boubou, pantalon = c["lignes"]
    assert boubou["prix_unitaire"] == 35_000 and boubou["sous_total"] == 70_000
    assert boubou["type_vetement_nom"] == "Boubou"
    assert pantalon["prix_unitaire"] == 10_000
    # RG8 : date de commande + plus long délai (boubou : 10 jours)
    assert c["date_commande"] == AUJOURD_HUI.isoformat()
    assert c["date_livraison_prevue"] == (AUJOURD_HUI + timedelta(days=10)).isoformat()
    # RG9 : rattachement automatique aux dernières mesures
    assert c["mesure_id"] == mesures_fatou[1].id
    # Statut initial, auteur, détail complet
    assert c["statut"] == "en_attente"
    assert c["cree_par_id"] == accueil.id
    assert c["client_nom"] == "Fatou Diop"
    assert c["paiements"] == [] and c["livraison"] is None and c["en_retard"] is False


def test_rg15_la_creation_inscrit_la_premiere_ligne_d_historique(client, h_accueil, accueil, catalogue, fatou):
    c = creer(client, h_accueil, corps_demo(catalogue, fatou))
    hist = client.get(f"{URL}/{c['id']}/historique", headers=h_accueil).json()
    assert len(hist) == 1
    assert hist[0]["ancien_statut"] is None and hist[0]["nouveau_statut"] == "en_attente"
    assert hist[0]["utilisateur_id"] == accueil.id


def test_rg5_numeros_uniques_et_successifs(client, h_accueil, catalogue, fatou):
    a = creer(client, h_accueil, corps_demo(catalogue, fatou))
    b = creer(client, h_accueil, corps_demo(catalogue, fatou))
    assert a["numero"] != b["numero"]
    assert int(b["numero"][-5:]) == int(a["numero"][-5:]) + 1


def test_rg6_prestation_inactive_422(client, h_accueil, catalogue, fatou):
    corps = corps_demo(catalogue, fatou, lignes=[{"type_vetement_id": catalogue["retiree"].id}])
    r = client.post(URL, json=corps, headers=h_accueil)
    assert r.status_code == 422
    assert "Ancienne tenue" in r.json()["detail"]


def test_prestation_inconnue_404(client, h_accueil, catalogue, fatou):
    corps = corps_demo(catalogue, fatou, lignes=[{"type_vetement_id": 99999}])
    assert client.post(URL, json=corps, headers=h_accueil).status_code == 404


def test_quantite_par_defaut_1(client, h_accueil, catalogue, fatou):
    c = creer(client, h_accueil, corps_demo(catalogue, fatou, remise=0,
                                            lignes=[{"type_vetement_id": catalogue["retouche"].id}]))
    assert c["lignes"][0]["quantite"] == 1 and c["montant_total"] == 3_000


def test_rg7_remise_superieure_aux_prestations_422(client, h_accueil, catalogue, fatou):
    r = client.post(URL, json=corps_demo(catalogue, fatou, remise=80_001), headers=h_accueil)
    assert r.status_code == 422
    assert "remise" in r.json()["detail"]


def test_rg7_remise_egale_aux_prestations_acceptee(client, h_accueil, catalogue, fatou):
    assert creer(client, h_accueil, corps_demo(catalogue, fatou, remise=80_000))["montant_total"] == 0


def test_rg8_date_prevue_fournie(client, h_accueil, catalogue, fatou):
    prevue = (AUJOURD_HUI + timedelta(days=3)).isoformat()
    c = creer(client, h_accueil, corps_demo(catalogue, fatou, date_livraison_prevue=prevue))
    assert c["date_livraison_prevue"] == prevue


def test_rg8_date_prevue_avant_la_commande_422(client, h_accueil, catalogue, fatou):
    hier = (AUJOURD_HUI - timedelta(days=1)).isoformat()
    r = client.post(URL, json=corps_demo(catalogue, fatou, date_livraison_prevue=hier), headers=h_accueil)
    assert r.status_code == 422


def test_rg9_mesures_d_un_autre_client_422(client, db, h_accueil, tailleur, catalogue, fatou):
    autre = Client(nom="Ba", prenom="Ibou", telephone="780000000")
    db.add(autre)
    db.flush()
    m = Mesure(client_id=autre.id, date_prise=AUJOURD_HUI, prise_par_id=tailleur.id, tour_cou=40)
    db.add(m)
    db.commit()
    r = client.post(URL, json=corps_demo(catalogue, fatou, mesure_id=m.id), headers=h_accueil)
    assert r.status_code == 422


def test_rg9_mesures_choisies_explicitement(client, h_accueil, catalogue, fatou, mesures_fatou):
    ancienne = mesures_fatou[0]
    c = creer(client, h_accueil, corps_demo(catalogue, fatou, mesure_id=ancienne.id))
    assert c["mesure_id"] == ancienne.id


def test_rg9_client_sans_mesures(client, h_accueil, catalogue, fatou):
    assert creer(client, h_accueil, corps_demo(catalogue, fatou))["mesure_id"] is None


@pytest.mark.parametrize("modif", [
    {"lignes": []}, {"remise": -1}, {"client_id": None},
])
def test_corps_invalide_422(client, h_accueil, catalogue, fatou, modif):
    assert client.post(URL, json=corps_demo(catalogue, fatou, **modif), headers=h_accueil).status_code == 422


@pytest.mark.parametrize("ligne", [{"quantite": 0}, {"prix_unitaire": 0}, {"prix_unitaire": -100}])
def test_ligne_invalide_422(client, h_accueil, catalogue, fatou, ligne):
    corps = corps_demo(catalogue, fatou, lignes=[{"type_vetement_id": catalogue["boubou"].id, **ligne}])
    assert client.post(URL, json=corps, headers=h_accueil).status_code == 422


def test_client_inconnu_404(client, h_accueil, catalogue, fatou):
    corps = corps_demo(catalogue, fatou, client_id=99999)
    assert client.post(URL, json=corps, headers=h_accueil).status_code == 404


def test_droits_le_tailleur_ne_cree_pas_de_commande(client, h_tailleur, catalogue, fatou):
    assert client.post(URL, json=corps_demo(catalogue, fatou), headers=h_tailleur).status_code == 403


def test_droits_l_admin_peut_creer(client, h_admin, catalogue, fatou):
    creer(client, h_admin, corps_demo(catalogue, fatou))


# --- Routes 25 et 26 : liste et détail ------------------------------------------------------

def test_liste_filtres_et_champs(client, db, h_tailleur, h_accueil, catalogue, fatou):
    a = creer(client, h_accueil, corps_demo(catalogue, fatou))
    b = creer(client, h_accueil, corps_demo(catalogue, fatou))
    # b passe en retard : date prévue dépassée (RG11)
    cmd_b = db.get(Commande, b["id"])
    cmd_b.date_commande = AUJOURD_HUI - timedelta(days=20)
    cmd_b.date_livraison_prevue = AUJOURD_HUI - timedelta(days=1)
    db.commit()
    statut(client, h_accueil, a["id"], "en_coupe")

    tout = client.get(URL, headers=h_tailleur).json()
    assert tout["total"] == 2
    assert [c["id"] for c in tout["items"]] == [a["id"], b["id"]]  # plus récente d'abord
    premier = tout["items"][0]
    assert {"client_nom", "solde", "en_retard"} <= set(premier)
    assert premier["client_nom"] == "Fatou Diop"

    filtre = lambda **p: [c["id"] for c in client.get(URL, params=p, headers=h_tailleur).json()["items"]]
    assert filtre(statut="en_coupe") == [a["id"]]
    assert filtre(en_retard="true") == [b["id"]]
    assert filtre(en_retard="false") == [a["id"]]
    assert filtre(client_id=fatou.id) == [a["id"], b["id"]]
    assert filtre(client_id=99999) == []
    assert filtre(numero=b["numero"]) == [b["id"]]
    assert filtre(date_min=AUJOURD_HUI.isoformat()) == [a["id"]]
    assert filtre(date_max=(AUJOURD_HUI - timedelta(days=1)).isoformat()) == [b["id"]]
    assert client.get(URL, params={"date_min": "2026-02-01", "date_max": "2026-01-01"},
                      headers=h_tailleur).status_code == 422


def test_liste_paginee(client, h_accueil, catalogue, fatou):
    for _ in range(3):
        creer(client, h_accueil, corps_demo(catalogue, fatou))
    corps = client.get(URL, params={"limit": 2, "offset": 2}, headers=h_accueil).json()
    assert corps["total"] == 3 and len(corps["items"]) == 1 and corps["limit"] == 2


def test_detail_et_404(client, h_tailleur, h_accueil, catalogue, fatou):
    c = creer(client, h_accueil, corps_demo(catalogue, fatou))
    detail = client.get(f"{URL}/{c['id']}", headers=h_tailleur).json()
    assert detail["lignes"][0]["sous_total"] == 70_000
    assert {"paiements", "livraison", "solde", "en_retard"} <= set(detail)
    assert client.get(f"{URL}/99999", headers=h_tailleur).status_code == 404


# --- Route 27 : modification -----------------------------------------------------------------

def test_patch_recalcule_les_montants(client, h_accueil, catalogue, fatou):
    c = creer(client, h_accueil, corps_demo(catalogue, fatou))
    r = client.patch(f"{URL}/{c['id']}", json={"remise": 0, "notes": "Urgent"}, headers=h_accueil)
    assert r.status_code == 200
    assert r.json()["montant_total"] == 80_000 and r.json()["notes"] == "Urgent"


def test_patch_rg7_remise_trop_forte_422(client, h_accueil, catalogue, fatou):
    c = creer(client, h_accueil, corps_demo(catalogue, fatou))
    assert client.patch(f"{URL}/{c['id']}", json={"remise": 90_000}, headers=h_accueil).status_code == 422


def test_patch_rg7_total_sous_le_montant_paye_409(client, db, h_accueil, accueil, catalogue, fatou):
    c = creer(client, h_accueil, corps_demo(catalogue, fatou, remise=0))  # total 80 000
    payer(db, c["id"], 60_000, accueil.id)
    r = client.patch(f"{URL}/{c['id']}", json={"remise": 30_000}, headers=h_accueil)  # 50 000 < 60 000
    assert r.status_code == 409
    assert client.get(f"{URL}/{c['id']}", headers=h_accueil).json()["remise"] == 0


def test_patch_date_et_mesures(client, db, h_accueil, tailleur, catalogue, fatou, mesures_fatou):
    c = creer(client, h_accueil, corps_demo(catalogue, fatou))
    prevue = (AUJOURD_HUI + timedelta(days=20)).isoformat()
    r = client.patch(f"{URL}/{c['id']}", json={"date_livraison_prevue": prevue,
                                               "mesure_id": mesures_fatou[0].id}, headers=h_accueil)
    assert r.status_code == 200
    assert r.json()["date_livraison_prevue"] == prevue and r.json()["mesure_id"] == mesures_fatou[0].id

    hier = (AUJOURD_HUI - timedelta(days=1)).isoformat()
    assert client.patch(f"{URL}/{c['id']}", json={"date_livraison_prevue": hier},
                        headers=h_accueil).status_code == 422  # RG8
    autre = Client(nom="Ba", prenom="Ibou", telephone="780000000")
    db.add(autre)
    db.flush()
    m = Mesure(client_id=autre.id, date_prise=AUJOURD_HUI, prise_par_id=tailleur.id, tour_cou=40)
    db.add(m)
    db.commit()
    assert client.patch(f"{URL}/{c['id']}", json={"mesure_id": m.id}, headers=h_accueil).status_code == 422


@pytest.mark.parametrize("corps", [{"remise": None}, {"date_livraison_prevue": None}, {"remise": -5}])
def test_patch_invalide_422(client, h_accueil, catalogue, fatou, corps):
    c = creer(client, h_accueil, corps_demo(catalogue, fatou))
    assert client.patch(f"{URL}/{c['id']}", json=corps, headers=h_accueil).status_code == 422


def test_patch_rg12_commande_annulee_409(client, h_accueil, catalogue, fatou):
    c = creer(client, h_accueil, corps_demo(catalogue, fatou))
    statut(client, h_accueil, c["id"], "annulee")
    assert client.patch(f"{URL}/{c['id']}", json={"notes": "x"}, headers=h_accueil).status_code == 409


def test_patch_rg12_commande_livree_409(client, db, h_accueil, catalogue, fatou):
    c = creer(client, h_accueil, corps_demo(catalogue, fatou))
    db.get(Commande, c["id"]).statut = "livree"
    db.commit()
    assert client.patch(f"{URL}/{c['id']}", json={"notes": "x"}, headers=h_accueil).status_code == 409


def test_patch_droits_et_404(client, h_tailleur, h_accueil, catalogue, fatou):
    c = creer(client, h_accueil, corps_demo(catalogue, fatou))
    assert client.patch(f"{URL}/{c['id']}", json={"notes": "x"}, headers=h_tailleur).status_code == 403
    assert client.patch(f"{URL}/99999", json={"notes": "x"}, headers=h_accueil).status_code == 404


# --- Routes 28 et 29 : workflow et historique --------------------------------------------------

def test_scenario_demo_etape_4_transition_interdite(client, h_accueil, catalogue, fatou):
    c = creer(client, h_accueil, corps_demo(catalogue, fatou))
    r = statut(client, h_accueil, c["id"], "terminee")
    assert r.status_code == 409
    assert r.json()["detail"] == (
        "Transition interdite : en_attente → terminee. Statuts possibles : annulee, en_coupe"
    )


def test_scenario_demo_etape_5_production_avec_essayage_retouches(
    client, h_accueil, h_tailleur, tailleur, catalogue, fatou
):
    c = creer(client, h_accueil, corps_demo(catalogue, fatou))
    parcours = ["en_coupe", "en_couture", "essayage", "retouches", "essayage", "terminee"]
    for nouveau in parcours:
        r = statut(client, h_tailleur, c["id"], nouveau, commentaire=f"passage {nouveau}")
        assert r.status_code == 200, r.json()
        assert r.json()["statut"] == nouveau

    hist = client.get(f"{URL}/{c['id']}/historique", headers=h_accueil).json()
    assert [(h["ancien_statut"], h["nouveau_statut"]) for h in hist] == [
        (None, "en_attente"),
        ("en_attente", "en_coupe"),
        ("en_coupe", "en_couture"),
        ("en_couture", "essayage"),
        ("essayage", "retouches"),
        ("retouches", "essayage"),
        ("essayage", "terminee"),
    ]
    assert all(h["utilisateur_id"] == tailleur.id for h in hist[1:])
    assert hist[-1]["commentaire"] == "passage terminee"
    assert hist[-1]["utilisateur_nom"] == tailleur.nom_complet


@pytest.mark.parametrize("actuel, interdit, possibles", [
    ("en_coupe", "essayage", "annulee, en_couture"),
    ("en_couture", "retouches", "annulee, essayage, terminee"),
    ("terminee", "en_coupe", "livree (uniquement par la confirmation de livraison)"),
])
def test_workflow_transitions_interdites(client, db, h_accueil, catalogue, fatou, actuel, interdit, possibles):
    c = creer(client, h_accueil, corps_demo(catalogue, fatou))
    db.get(Commande, c["id"]).statut = actuel
    db.commit()
    r = statut(client, h_accueil, c["id"], interdit)
    assert r.status_code == 409
    assert r.json()["detail"].endswith(f"Statuts possibles : {possibles}")


def test_rg13_meme_statut_409(client, h_accueil, catalogue, fatou):
    c = creer(client, h_accueil, corps_demo(catalogue, fatou))
    assert statut(client, h_accueil, c["id"], "en_attente").status_code == 409


def test_rg13_livree_interdit_par_cette_route(client, db, h_accueil, catalogue, fatou):
    c = creer(client, h_accueil, corps_demo(catalogue, fatou))
    db.get(Commande, c["id"]).statut = "terminee"
    db.commit()
    r = statut(client, h_accueil, c["id"], "livree")
    assert r.status_code == 409
    assert "confirmation de livraison" in r.json()["detail"]


@pytest.mark.parametrize("final", ["livree", "annulee"])
def test_statuts_finaux_plus_aucune_transition(client, db, h_accueil, catalogue, fatou, final):
    c = creer(client, h_accueil, corps_demo(catalogue, fatou))
    db.get(Commande, c["id"]).statut = final
    db.commit()
    r = statut(client, h_accueil, c["id"], "en_coupe")
    assert r.status_code == 409
    assert "aucun" in r.json()["detail"]


def test_rg14_le_tailleur_ne_peut_pas_annuler(client, h_accueil, h_tailleur, catalogue, fatou):
    c = creer(client, h_accueil, corps_demo(catalogue, fatou))
    assert statut(client, h_tailleur, c["id"], "annulee").status_code == 403


def test_l_accueil_peut_annuler_sans_acompte(client, h_accueil, catalogue, fatou):
    c = creer(client, h_accueil, corps_demo(catalogue, fatou))
    r = statut(client, h_accueil, c["id"], "annulee")
    assert r.status_code == 200 and r.json()["statut"] == "annulee"


def test_rg14_annuler_avec_acompte_exige_un_commentaire(client, db, h_accueil, accueil, catalogue, fatou):
    c = creer(client, h_accueil, corps_demo(catalogue, fatou))
    payer(db, c["id"], 20_000, accueil.id)
    assert statut(client, h_accueil, c["id"], "annulee").status_code == 422
    assert statut(client, h_accueil, c["id"], "annulee", commentaire="   ").status_code == 422
    r = statut(client, h_accueil, c["id"], "annulee", commentaire="Remboursé en espèces")
    assert r.status_code == 200
    hist = client.get(f"{URL}/{c['id']}/historique", headers=h_accueil).json()
    assert hist[-1]["commentaire"] == "Remboursé en espèces"


def test_statut_inconnu_422_et_commande_404(client, h_accueil, catalogue, fatou):
    c = creer(client, h_accueil, corps_demo(catalogue, fatou))
    assert statut(client, h_accueil, c["id"], "expediee").status_code == 422
    assert statut(client, h_accueil, 99999, "en_coupe").status_code == 404
    assert client.get(f"{URL}/99999/historique", headers=h_accueil).status_code == 404


# --- Routes 30 et 31 : lignes (RG10) ------------------------------------------------------------

def test_ajouter_une_ligne_recalcule(client, h_accueil, catalogue, fatou):
    c = creer(client, h_accueil, corps_demo(catalogue, fatou))
    r = client.post(f"{URL}/{c['id']}/lignes", json={"type_vetement_id": catalogue["retouche"].id,
                                                      "quantite": 2}, headers=h_accueil)
    assert r.status_code == 201
    assert len(r.json()["lignes"]) == 3
    assert r.json()["montant_total"] == 75_000 + 6_000


def test_ajouter_ligne_prestation_inactive_422(client, h_accueil, catalogue, fatou):
    c = creer(client, h_accueil, corps_demo(catalogue, fatou))
    r = client.post(f"{URL}/{c['id']}/lignes", json={"type_vetement_id": catalogue["retiree"].id},
                    headers=h_accueil)
    assert r.status_code == 422


def test_rg10_lignes_figees_hors_en_attente_409(client, h_accueil, catalogue, fatou):
    c = creer(client, h_accueil, corps_demo(catalogue, fatou))
    statut(client, h_accueil, c["id"], "en_coupe")
    ligne_id = c["lignes"][0]["id"]
    assert client.post(f"{URL}/{c['id']}/lignes", json={"type_vetement_id": catalogue["retouche"].id},
                       headers=h_accueil).status_code == 409
    assert client.delete(f"{URL}/{c['id']}/lignes/{ligne_id}", headers=h_accueil).status_code == 409


def test_rg12_lignes_d_une_commande_annulee_409(client, h_accueil, catalogue, fatou):
    c = creer(client, h_accueil, corps_demo(catalogue, fatou))
    statut(client, h_accueil, c["id"], "annulee")
    assert client.post(f"{URL}/{c['id']}/lignes", json={"type_vetement_id": catalogue["retouche"].id},
                       headers=h_accueil).status_code == 409


def test_retirer_une_ligne(client, h_accueil, catalogue, fatou):
    c = creer(client, h_accueil, corps_demo(catalogue, fatou))
    pantalon_id = c["lignes"][1]["id"]
    r = client.delete(f"{URL}/{c['id']}/lignes/{pantalon_id}", headers=h_accueil)
    assert r.status_code == 200
    assert [l["type_vetement_nom"] for l in r.json()["lignes"]] == ["Boubou"]
    assert r.json()["montant_total"] == 70_000 - 5_000


def test_rg10_une_commande_garde_au_moins_une_ligne_409(client, h_accueil, catalogue, fatou):
    c = creer(client, h_accueil, corps_demo(catalogue, fatou, remise=0,
                                            lignes=[{"type_vetement_id": catalogue["boubou"].id}]))
    r = client.delete(f"{URL}/{c['id']}/lignes/{c['lignes'][0]['id']}", headers=h_accueil)
    assert r.status_code == 409


def test_rg7_retirer_une_ligne_sous_le_montant_paye_409(client, db, h_accueil, accueil, catalogue, fatou):
    c = creer(client, h_accueil, corps_demo(catalogue, fatou, remise=0))  # 80 000
    payer(db, c["id"], 75_000, accueil.id)
    r = client.delete(f"{URL}/{c['id']}/lignes/{c['lignes'][1]['id']}", headers=h_accueil)  # → 70 000
    assert r.status_code == 409


def test_retirer_ligne_inconnue_404(client, h_accueil, catalogue, fatou):
    a = creer(client, h_accueil, corps_demo(catalogue, fatou))
    b = creer(client, h_accueil, corps_demo(catalogue, fatou))
    assert client.delete(f"{URL}/{a['id']}/lignes/99999", headers=h_accueil).status_code == 404
    # Une ligne d'une autre commande est introuvable dans celle-ci.
    assert client.delete(f"{URL}/{a['id']}/lignes/{b['lignes'][0]['id']}", headers=h_accueil).status_code == 404


def test_droits_lignes_reservees_a_l_accueil(client, h_accueil, h_tailleur, catalogue, fatou):
    c = creer(client, h_accueil, corps_demo(catalogue, fatou))
    assert client.post(f"{URL}/{c['id']}/lignes", json={"type_vetement_id": catalogue["retouche"].id},
                       headers=h_tailleur).status_code == 403
    assert client.delete(f"{URL}/{c['id']}/lignes/{c['lignes'][0]['id']}",
                         headers=h_tailleur).status_code == 403


def test_droits_sans_jeton_401(client):
    assert client.get(URL).status_code == 401
    assert client.post(URL, json={}).status_code == 401
