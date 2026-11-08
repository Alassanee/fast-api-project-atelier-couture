"""Statistiques : routes 39 à 43 (administrateur uniquement)."""

from datetime import date, timedelta

import pytest

from app.enums import ModeLivraison, ModePaiement, StatutCommande
from app.models import Client, Commande, LigneCommande, Livraison, Paiement

API = "/api/v1/statistiques"
AUJOURD_HUI = date.today()
DEBUT_MOIS = AUJOURD_HUI.replace(day=1)
MOIS_DERNIER = DEBUT_MOIS - timedelta(days=1)  # dernier jour du mois précédent


@pytest.fixture
def ibou(db):
    c = Client(nom="Ba", prenom="Ibou", telephone="780000000")
    db.add(c)
    db.commit()
    return c


@pytest.fixture
def inserer(db, accueil):
    """Insère une commande avec des dates arbitraires (passé, autre mois...)."""
    def _inserer(client, lignes, *, le=AUJOURD_HUI, statut=StatutCommande.en_attente, remise=0,
                 paiements=(), prevue=None):
        commande = Commande(
            client_id=client.id, statut=statut, date_commande=le,
            date_livraison_prevue=prevue or le + timedelta(days=7), remise=remise, cree_par_id=accueil.id,
        )
        for prestation, quantite, prix in lignes:
            commande.lignes.append(LigneCommande(type_vetement_id=prestation.id, quantite=quantite,
                                                 prix_unitaire=prix))
        for montant, jour in paiements:
            commande.paiements.append(Paiement(montant=montant, mode=ModePaiement.especes,
                                               date_paiement=jour, enregistre_par_id=accueil.id))
        commande.montant_total = sum(q * p for _, q, p in lignes) - remise
        commande.montant_paye = sum(m for m, _ in paiements)
        db.add(commande)
        db.flush()
        commande.numero = f"CMD-{le.year}-{commande.id:05d}"
        db.commit()
        return commande
    return _inserer


# --- Route 39 : tableau de bord -------------------------------------------------------------

def test_tableau_de_bord_vide_tous_les_statuts_a_zero(client, h_admin):
    r = client.get(f"{API}/tableau-de-bord", headers=h_admin)
    assert r.status_code == 200
    t = r.json()
    assert t["mois"] == DEBUT_MOIS.strftime("%Y-%m")
    assert t["chiffre_affaires_mois"] == 0 and t["encaisse_mois"] == 0 and t["nb_commandes_mois"] == 0
    assert t["commandes_par_statut"] == {s.value: 0 for s in StatutCommande}
    assert t["commandes_pretes_a_livrer"] == [] and t["livraisons_du_jour"] == []


def test_scenario_demo_etape_9_le_ca_du_mois_augmente(client, h_admin, h_accueil, catalogue, fatou):
    avant = client.get(f"{API}/tableau-de-bord", headers=h_admin).json()
    r = client.post("/api/v1/commandes", json={
        "client_id": fatou.id, "remise": 5_000,
        "lignes": [{"type_vetement_id": catalogue["boubou"].id, "quantite": 2},
                   {"type_vetement_id": catalogue["pantalon"].id, "prix_unitaire": 10_000}],
    }, headers=h_accueil)
    apres = client.get(f"{API}/tableau-de-bord", headers=h_admin).json()
    assert apres["chiffre_affaires_mois"] == avant["chiffre_affaires_mois"] + r.json()["montant_total"]
    assert apres["nb_commandes_mois"] == avant["nb_commandes_mois"] + 1


def test_scenario_demo_etape_9_l_accueil_recoit_403(client, h_accueil):
    assert client.get(f"{API}/tableau-de-bord", headers=h_accueil).status_code == 403


def test_tableau_de_bord_indicateurs(client, db, h_admin, inserer, catalogue, fatou, ibou):
    boubou, robe = catalogue["boubou"], catalogue["pantalon"]
    # Ce mois-ci : 70 000 avec 20 000 payés ce mois
    inserer(fatou, [(boubou, 2, 35_000)], paiements=[(20_000, AUJOURD_HUI)])
    # Ce mois-ci, mais annulée : exclue du CA et du reste à encaisser
    inserer(ibou, [(boubou, 1, 35_000)], statut=StatutCommande.annulee, paiements=[(5_000, AUJOURD_HUI)])
    # Mois dernier : 12 000 dont 2 000 payés le mois dernier et 4 000 ce mois-ci ; en retard
    inserer(ibou, [(robe, 1, 12_000)], le=MOIS_DERNIER, statut=StatutCommande.en_couture,
            paiements=[(2_000, MOIS_DERNIER), (4_000, AUJOURD_HUI)], prevue=MOIS_DERNIER)
    # Terminée, livrable aujourd'hui
    prete = inserer(fatou, [(robe, 1, 12_000)], le=MOIS_DERNIER, statut=StatutCommande.terminee,
                    paiements=[(12_000, MOIS_DERNIER)], prevue=AUJOURD_HUI)
    db.add(Livraison(commande_id=prete.id, mode=ModeLivraison.retrait_atelier, date_prevue=AUJOURD_HUI))
    db.commit()

    t = client.get(f"{API}/tableau-de-bord", headers=h_admin).json()
    assert t["chiffre_affaires_mois"] == 70_000
    assert t["nb_commandes_mois"] == 1
    assert t["encaisse_mois"] == 20_000 + 5_000 + 4_000  # paiements reçus ce mois-ci
    assert t["reste_a_encaisser"] == (70_000 - 20_000) + (12_000 - 6_000) + 0
    assert t["commandes_par_statut"]["en_attente"] == 1
    assert t["commandes_par_statut"]["annulee"] == 1
    assert t["commandes_par_statut"]["en_couture"] == 1
    assert t["commandes_par_statut"]["terminee"] == 1
    assert t["commandes_par_statut"]["livree"] == 0
    assert t["nb_commandes_en_retard"] == 1
    assert [c["id"] for c in t["commandes_pretes_a_livrer"]] == [prete.id]
    assert [l["commande_id"] for l in t["livraisons_du_jour"]] == [prete.id]


# --- Route 40 : chiffre d'affaires ------------------------------------------------------------

def test_chiffre_affaires_par_jour_et_par_mois(client, h_admin, inserer, catalogue, fatou):
    boubou = catalogue["boubou"]
    j1, j2 = date(2026, 3, 10), date(2026, 3, 25)
    inserer(fatou, [(boubou, 1, 35_000)], le=j1, paiements=[(10_000, j1), (5_000, j2)])
    inserer(fatou, [(boubou, 2, 30_000)], le=j2, remise=4_000)
    inserer(fatou, [(boubou, 1, 99_000)], le=j2, statut=StatutCommande.annulee)  # exclue du CA
    inserer(fatou, [(boubou, 1, 50_000)], le=date(2026, 4, 2), paiements=[(50_000, date(2026, 4, 2))])

    params = {"date_debut": "2026-03-01", "date_fin": "2026-04-30"}
    r = client.get(f"{API}/chiffre-affaires", params={**params, "granularite": "jour"}, headers=h_admin)
    assert r.status_code == 200
    jour = r.json()
    assert jour["periodes"] == [  # seules les périodes avec activité
        {"periode": "2026-03-10", "chiffre_affaires": 35_000, "encaisse": 10_000},
        {"periode": "2026-03-25", "chiffre_affaires": 56_000, "encaisse": 5_000},
        {"periode": "2026-04-02", "chiffre_affaires": 50_000, "encaisse": 50_000},
    ]
    assert jour["total_chiffre_affaires"] == 141_000 and jour["total_encaisse"] == 65_000

    mois = client.get(f"{API}/chiffre-affaires", params={**params, "granularite": "mois"},
                      headers=h_admin).json()
    assert mois["periodes"] == [
        {"periode": "2026-03", "chiffre_affaires": 91_000, "encaisse": 15_000},
        {"periode": "2026-04", "chiffre_affaires": 50_000, "encaisse": 50_000},
    ]


def test_chiffre_affaires_periode_par_defaut(client, h_admin, inserer, catalogue, fatou):
    inserer(fatou, [(catalogue["boubou"], 1, 35_000)], le=MOIS_DERNIER)  # hors période par défaut
    inserer(fatou, [(catalogue["boubou"], 1, 30_000)])
    r = client.get(f"{API}/chiffre-affaires", headers=h_admin).json()
    assert r["granularite"] == "jour"
    assert r["date_debut"] == DEBUT_MOIS.isoformat() and r["date_fin"] == AUJOURD_HUI.isoformat()
    assert r["total_chiffre_affaires"] == 30_000


def test_chiffre_affaires_dates_inversees_422(client, h_admin):
    r = client.get(f"{API}/chiffre-affaires", params={"date_debut": "2026-05-01", "date_fin": "2026-04-01"},
                   headers=h_admin)
    assert r.status_code == 422


def test_chiffre_affaires_granularite_invalide_422(client, h_admin):
    assert client.get(f"{API}/chiffre-affaires", params={"granularite": "annee"},
                      headers=h_admin).status_code == 422


# --- Route 41 : par type de vêtement -----------------------------------------------------------

def test_types_vetement_avant_remise_du_plus_eleve_au_plus_faible(client, h_admin, inserer, catalogue, fatou):
    boubou, pantalon, retouche = catalogue["boubou"], catalogue["pantalon"], catalogue["retouche"]
    inserer(fatou, [(boubou, 2, 35_000), (pantalon, 1, 10_000)], remise=5_000)
    inserer(fatou, [(pantalon, 3, 12_000), (retouche, 4, 3_000)])
    inserer(fatou, [(retouche, 50, 3_000)], statut=StatutCommande.annulee)  # exclue
    inserer(fatou, [(boubou, 5, 35_000)], le=MOIS_DERNIER)  # hors période par défaut

    stats = client.get(f"{API}/types-vetement", headers=h_admin).json()
    assert [(s["nom"], s["quantite_vendue"], s["chiffre_affaires"]) for s in stats] == [
        ("Boubou", 2, 70_000),  # avant remise
        ("Pantalon", 4, 46_000),
        ("Retouche", 4, 12_000),
    ]


def test_types_vetement_dates_inversees_422(client, h_admin):
    r = client.get(f"{API}/types-vetement", params={"date_debut": "2026-05-01", "date_fin": "2026-04-01"},
                   headers=h_admin)
    assert r.status_code == 422


# --- Route 42 : meilleurs clients ---------------------------------------------------------------

def test_top_clients(client, db, h_admin, inserer, catalogue, fatou, ibou):
    boubou = catalogue["boubou"]
    awa = Client(nom="Sow", prenom="Awa", telephone="760000000")
    db.add(awa)
    db.commit()
    inserer(fatou, [(boubou, 1, 35_000)], paiements=[(35_000, AUJOURD_HUI)])
    inserer(fatou, [(boubou, 1, 35_000)], paiements=[(10_000, AUJOURD_HUI)])
    inserer(ibou, [(boubou, 3, 35_000)])
    inserer(awa, [(boubou, 1, 20_000)])
    inserer(awa, [(boubou, 9, 35_000)], statut=StatutCommande.annulee)  # exclue

    top = client.get(f"{API}/top-clients", headers=h_admin).json()
    assert [(t["client_nom"], t["nb_commandes"], t["chiffre_affaires"], t["solde_du"]) for t in top] == [
        ("Ibou Ba", 1, 105_000, 105_000),
        ("Fatou Diop", 2, 70_000, 25_000),
        ("Awa Sow", 1, 20_000, 20_000),
    ]
    assert top[0]["telephone"] == "780000000"
    assert len(client.get(f"{API}/top-clients", params={"limite": 2}, headers=h_admin).json()) == 2
    assert client.get(f"{API}/top-clients", params={"limite": 0}, headers=h_admin).status_code == 422


# --- Route 43 : impayés ------------------------------------------------------------------------

def test_scenario_demo_etape_10_impayes_les_plus_urgents_d_abord(
    client, h_admin, inserer, catalogue, fatou, ibou
):
    boubou = catalogue["boubou"]
    tard = inserer(fatou, [(boubou, 1, 35_000)], prevue=AUJOURD_HUI + timedelta(days=20))
    urgent = inserer(ibou, [(boubou, 1, 35_000)], paiements=[(5_000, AUJOURD_HUI)],
                     prevue=AUJOURD_HUI + timedelta(days=2))
    en_retard = inserer(ibou, [(boubou, 1, 35_000)], le=MOIS_DERNIER, prevue=MOIS_DERNIER,
                        statut=StatutCommande.en_coupe)
    livree_avec_dette = inserer(fatou, [(boubou, 1, 35_000)], statut=StatutCommande.livree,
                                paiements=[(30_000, AUJOURD_HUI)], prevue=AUJOURD_HUI)
    inserer(fatou, [(boubou, 1, 35_000)], paiements=[(35_000, AUJOURD_HUI)])  # soldée : exclue
    inserer(fatou, [(boubou, 1, 35_000)], statut=StatutCommande.annulee)  # annulée : exclue

    r = client.get(f"{API}/impayes", headers=h_admin).json()
    assert r["total"] == 4 and r["limit"] == 20 and r["offset"] == 0
    assert [c["id"] for c in r["items"]] == [en_retard.id, livree_avec_dette.id, urgent.id, tard.id]
    assert r["items"][0]["en_retard"] is True
    assert r["items"][1]["solde"] == 5_000

    page = client.get(f"{API}/impayes", params={"limit": 1, "offset": 1}, headers=h_admin).json()
    assert [c["id"] for c in page["items"]] == [livree_avec_dette.id]

    # Étape 10 : liste des commandes en retard
    retard = client.get("/api/v1/commandes", params={"en_retard": "true"}, headers=h_admin).json()
    assert [c["id"] for c in retard["items"]] == [en_retard.id]


# --- Droits ------------------------------------------------------------------------------------

ROUTES = ["tableau-de-bord", "chiffre-affaires", "types-vetement", "top-clients", "impayes"]


@pytest.mark.parametrize("route", ROUTES)
@pytest.mark.parametrize("role", ["accueil", "tailleur"])
def test_droits_statistiques_reservees_a_l_admin(client, request, route, role):
    h = request.getfixturevalue(f"h_{role}")
    assert client.get(f"{API}/{route}", headers=h).status_code == 403


@pytest.mark.parametrize("route", ROUTES)
def test_droits_admin_et_sans_jeton(client, h_admin, route):
    assert client.get(f"{API}/{route}", headers=h_admin).status_code == 200
    assert client.get(f"{API}/{route}").status_code == 401
