"""Point d'entrée de l'API : création de l'application FastAPI."""

from fastapi import FastAPI

from app.config import settings

app = FastAPI(
    title=settings.app_name,
    description="Back-end de gestion d'un atelier de couture : clients, mesures, "
    "commandes, paiements, livraisons et statistiques.",
    version="1.0.0",
)

# Les routeurs (un fichier par domaine) seront inclus ici sous le préfixe /api/v1.
