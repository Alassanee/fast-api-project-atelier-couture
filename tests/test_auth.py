"""Authentification et sécurité : routes 1, 2, 44 et règles RG21 à RG23."""

from datetime import UTC, datetime, timedelta

import jwt

from app.config import settings
from app.enums import Role
from tests.conftest import MOT_DE_PASSE, entetes

LOGIN = "/api/v1/auth/login"
ME = "/api/v1/auth/me"


def connexion(client, email, mot_de_passe=MOT_DE_PASSE):
    return client.post(LOGIN, data={"username": email, "password": mot_de_passe})


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_login_renvoie_un_jeton(client, admin):
    r = connexion(client, admin.email)
    assert r.status_code == 200
    corps = r.json()
    assert corps["token_type"] == "bearer"
    assert corps["expires_in"] == settings.access_token_expire_minutes * 60
    assert corps["access_token"]


def test_login_insensible_a_la_casse(client, admin):
    assert connexion(client, admin.email.upper()).status_code == 200


def test_rg23_meme_message_quel_que_soit_l_echec(client, creer_utilisateur):
    actif = creer_utilisateur(Role.accueil)
    inactif = creer_utilisateur(Role.accueil, actif=False)
    reponses = [
        connexion(client, actif.email, "mauvais-mot-de-passe"),
        connexion(client, "inconnu@atelier.sn"),
        connexion(client, inactif.email),
    ]
    assert {r.status_code for r in reponses} == {401}
    assert len({r.json()["detail"] for r in reponses}) == 1


def test_me_ne_renvoie_aucune_donnee_sensible(client, admin):
    r = client.get(ME, headers=entetes(admin))
    assert r.status_code == 200
    corps = r.json()
    assert corps["email"] == admin.email
    assert "mot_de_passe_hash" not in corps
    assert "mot_de_passe" not in corps


def test_rg21_mot_de_passe_hache_argon2(admin):
    assert admin.mot_de_passe_hash.startswith("$argon2")
    assert MOT_DE_PASSE not in admin.mot_de_passe_hash


def test_401_sans_jeton(client):
    r = client.get(ME)
    assert r.status_code == 401
    assert "detail" in r.json()


def test_401_jeton_invalide(client):
    assert client.get(ME, headers={"Authorization": "Bearer nimportequoi"}).status_code == 401


def test_rg22_jeton_expire(client, admin):
    jeton = jwt.encode(
        {"sub": str(admin.id), "exp": datetime.now(UTC) - timedelta(seconds=1)},
        settings.secret_key, algorithm=settings.jwt_algorithm,
    )
    assert client.get(ME, headers={"Authorization": f"Bearer {jeton}"}).status_code == 401


def test_rg22_compte_desactive_refuse_meme_avec_jeton_valide(client, db, accueil):
    h = entetes(accueil)
    assert client.get(ME, headers=h).status_code == 200
    accueil.actif = False
    db.commit()
    assert client.get(ME, headers=h).status_code == 401


def test_erreur_de_validation_en_francais(client):
    r = client.post(LOGIN, data={"username": "x"})
    assert r.status_code == 422
    assert isinstance(r.json()["detail"], str)
    assert "obligatoire" in r.json()["detail"]
