"""Script d'initialisation : python -m app.seed

Crée le premier administrateur (variables ADMIN_EMAIL, ADMIN_PASSWORD,
ADMIN_NOM_COMPLET) et les prestations du catalogue de l'annexe B.
Peut être relancé sans créer de doublons.
"""

import sys

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal
from app.enums import Role
from app.models import TypeVetement, Utilisateur
from app.schemas.utilisateur import MOT_DE_PASSE_MIN
from app.security import hacher_mot_de_passe

# Annexe B : (nom, description, prix de base en FCFA, délai en jours)
CATALOGUE_DEPART: list[tuple[str, str, int, int]] = [
    ("Boubou", "Boubou homme en bazin ou brodé", 35_000, 10),
    ("Costume 2 pièces", "Veste et pantalon", 85_000, 14),
    ("Robe", "Robe sur mesure", 30_000, 7),
    ("Ensemble wax", "Tenue deux pièces en wax", 25_000, 7),
    ("Chemise", "Chemise sur mesure", 15_000, 5),
    ("Pantalon", "Pantalon sur mesure", 12_000, 4),
    ("Retouche", "Ourlet, rétrécissement, remplacement de fermeture", 3_000, 2),
]


def creer_admin(db: Session) -> None:
    email, mot_de_passe = settings.admin_email, settings.admin_password
    if not email or not mot_de_passe:
        print("ADMIN_EMAIL et ADMIN_PASSWORD doivent être définis dans le .env.")
        sys.exit(1)
    if len(mot_de_passe) < MOT_DE_PASSE_MIN:
        print(f"ADMIN_PASSWORD doit contenir au moins {MOT_DE_PASSE_MIN} caractères.")
        sys.exit(1)
    email = email.strip().lower()
    existant = db.scalar(select(Utilisateur).where(func.lower(Utilisateur.email) == email))
    if existant:
        print(f"- Administrateur {email} : déjà présent.")
        return
    db.add(
        Utilisateur(
            email=email,
            nom_complet=settings.admin_nom_complet,
            mot_de_passe_hash=hacher_mot_de_passe(mot_de_passe),
            role=Role.admin,
            actif=True,
        )
    )
    print(f"+ Administrateur {email} : créé.")


def creer_catalogue(db: Session) -> None:
    for nom, description, prix_base, delai_jours in CATALOGUE_DEPART:
        if db.scalar(select(TypeVetement).where(TypeVetement.nom == nom)):
            print(f"- Prestation « {nom} » : déjà présente.")
            continue
        db.add(
            TypeVetement(
                nom=nom, description=description, prix_base=prix_base,
                delai_jours=delai_jours, actif=True,
            )
        )
        print(f"+ Prestation « {nom} » : créée.")


def main() -> None:
    with SessionLocal() as db:
        creer_admin(db)
        creer_catalogue(db)
        db.commit()
    print("Initialisation terminée.")


if __name__ == "__main__":
    main()
