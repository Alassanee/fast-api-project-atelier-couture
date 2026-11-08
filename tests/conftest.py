"""Configuration pytest : base PostgreSQL de test, client HTTP et comptes par rôle.

La base de test (TEST_DATABASE_URL) est créée si besoin, son schéma est construit
par les migrations Alembic (comme en production), puis elle est vidée après chaque test.
"""

import os
from collections.abc import Callable, Iterator
from pathlib import Path

from dotenv import dotenv_values

RACINE = Path(__file__).resolve().parent.parent
_env = {**dotenv_values(RACINE / ".env"), **os.environ}
URL_PRINCIPALE = _env["DATABASE_URL"]
URL_TEST = _env.get("TEST_DATABASE_URL") or f"{URL_PRINCIPALE}_test"
if URL_TEST == URL_PRINCIPALE:
    raise RuntimeError("TEST_DATABASE_URL doit désigner une base différente de DATABASE_URL.")

# Doit être fait AVANT d'importer l'application : le moteur SQLAlchemy lit cette variable.
os.environ["DATABASE_URL"] = URL_TEST

import pytest  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, make_url, text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.database import Base, SessionLocal, engine  # noqa: E402
from app.enums import Role  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Client, TypeVetement, Utilisateur  # noqa: E402
from app.security import creer_jeton_acces, hacher_mot_de_passe  # noqa: E402

MOT_DE_PASSE = "motdepasse123"


def _creer_base_si_absente() -> None:
    nom_base = make_url(URL_TEST).database
    serveur = create_engine(make_url(URL_TEST).set(database="postgres"), isolation_level="AUTOCOMMIT")
    with serveur.connect() as conn:
        existe = conn.scalar(text("SELECT 1 FROM pg_database WHERE datname = :n"), {"n": nom_base})
        if not existe:
            conn.execute(text(f'CREATE DATABASE "{nom_base}"'))
    serveur.dispose()


@pytest.fixture(scope="session", autouse=True)
def base_de_test() -> Iterator[None]:
    _creer_base_si_absente()
    command.upgrade(Config(str(RACINE / "alembic.ini")), "head")
    yield
    engine.dispose()


@pytest.fixture(autouse=True)
def vider_tables() -> Iterator[None]:
    yield
    tables = ", ".join(f'"{t.name}"' for t in reversed(Base.metadata.sorted_tables))
    with engine.begin() as conn:
        conn.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))


@pytest.fixture
def db() -> Iterator[Session]:
    with SessionLocal() as session:
        yield session


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def creer_utilisateur(db: Session) -> Callable[..., Utilisateur]:
    compteur = {"n": 0}

    def _creer(role: Role = Role.accueil, actif: bool = True, email: str | None = None,
               nom_complet: str | None = None) -> Utilisateur:
        compteur["n"] += 1
        utilisateur = Utilisateur(
            email=email or f"{role.value}{compteur['n']}@atelier.sn",
            nom_complet=nom_complet or f"{role.value.capitalize()} {compteur['n']}",
            mot_de_passe_hash=hacher_mot_de_passe(MOT_DE_PASSE),
            role=role,
            actif=actif,
        )
        db.add(utilisateur)
        db.commit()
        return utilisateur

    return _creer


def entetes(utilisateur: Utilisateur) -> dict[str, str]:
    jeton, _ = creer_jeton_acces(utilisateur.id)
    return {"Authorization": f"Bearer {jeton}"}


@pytest.fixture
def admin(creer_utilisateur) -> Utilisateur:
    return creer_utilisateur(Role.admin, nom_complet="Admin Principal")


@pytest.fixture
def accueil(creer_utilisateur) -> Utilisateur:
    return creer_utilisateur(Role.accueil)


@pytest.fixture
def tailleur(creer_utilisateur) -> Utilisateur:
    return creer_utilisateur(Role.tailleur)


@pytest.fixture
def h_admin(admin) -> dict[str, str]:
    return entetes(admin)


@pytest.fixture
def h_accueil(accueil) -> dict[str, str]:
    return entetes(accueil)


@pytest.fixture
def h_tailleur(tailleur) -> dict[str, str]:
    return entetes(tailleur)


# --- Données métier communes ---------------------------------------------------------


@pytest.fixture
def catalogue(db: Session) -> dict[str, TypeVetement]:
    prestations = {
        "boubou": TypeVetement(nom="Boubou", prix_base=35_000, delai_jours=10),
        "pantalon": TypeVetement(nom="Pantalon", prix_base=12_000, delai_jours=4),
        "retouche": TypeVetement(nom="Retouche", prix_base=3_000, delai_jours=2),
        "retiree": TypeVetement(nom="Ancienne tenue", prix_base=9_000, delai_jours=3, actif=False),
    }
    db.add_all(prestations.values())
    db.commit()
    return prestations


@pytest.fixture
def fatou(db: Session) -> Client:
    cliente = Client(nom="Diop", prenom="Fatou", telephone="771234567", genre="femme")
    db.add(cliente)
    db.commit()
    return cliente
