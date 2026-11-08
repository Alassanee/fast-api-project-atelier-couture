"""Script d'initialisation : python -m app.seed [--demo]."""

import pytest

from app.config import settings
from app.enums import Role
from app.models import TypeVetement, Utilisateur
from app.seed import COMPTES_DEMO, main


@pytest.fixture
def config_seed(monkeypatch):
    monkeypatch.setattr(settings, "admin_email", "patron@atelier.sn")
    monkeypatch.setattr(settings, "admin_password", "patron-secret")
    monkeypatch.setattr(settings, "demo_password", "demo-secret")


def test_seed_cree_admin_et_catalogue_sans_doublon(client, db, config_seed):
    main([])
    main([])  # relancé : rien de plus
    utilisateurs = db.query(Utilisateur).all()
    assert [(u.email, u.role) for u in utilisateurs] == [("patron@atelier.sn", Role.admin)]
    assert db.query(TypeVetement).count() == 7
    r = client.post("/api/v1/auth/login", data={"username": "patron@atelier.sn", "password": "patron-secret"})
    assert r.status_code == 200


def test_seed_demo_cree_les_comptes_accueil_et_tailleur(client, db, config_seed):
    main(["--demo"])
    main(["--demo"])
    roles = {u.email: u.role for u in db.query(Utilisateur).all()}
    assert roles == {"patron@atelier.sn": Role.admin, **{e: r for e, _, r in COMPTES_DEMO}}
    for email, _, _ in COMPTES_DEMO:
        r = client.post("/api/v1/auth/login", data={"username": email, "password": "demo-secret"})
        assert r.status_code == 200


def test_seed_refuse_un_mot_de_passe_admin_trop_court(monkeypatch, config_seed):
    monkeypatch.setattr(settings, "admin_password", "court")
    with pytest.raises(SystemExit):
        main([])
