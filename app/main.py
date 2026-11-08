"""Point d'entrée de l'API : création de l'application FastAPI."""

from fastapi import FastAPI
from sqlalchemy import text

from app.config import settings
from app.dependencies import DbSession
from app.exceptions import installer_gestionnaires
from app.routers import (
    auth,
    catalogue,
    clients,
    commandes,
    livraisons,
    mesures,
    paiements,
    statistiques,
    utilisateurs,
)

app = FastAPI(
    title=settings.app_name,
    description="Back-end de gestion d'un atelier de couture : clients, mesures, "
    "commandes, paiements, livraisons et statistiques.",
    version="1.0.0",
)

installer_gestionnaires(app)

# Un routeur par domaine, tous sous le préfixe /api/v1.
app.include_router(auth.router, prefix=settings.api_prefix)
app.include_router(utilisateurs.router, prefix=settings.api_prefix)
app.include_router(clients.router, prefix=settings.api_prefix)
app.include_router(catalogue.router, prefix=settings.api_prefix)
app.include_router(mesures.router, prefix=settings.api_prefix)
app.include_router(commandes.router, prefix=settings.api_prefix)
app.include_router(paiements.router, prefix=settings.api_prefix)
app.include_router(livraisons.router, prefix=settings.api_prefix)
app.include_router(statistiques.router, prefix=settings.api_prefix)


@app.get("/health", tags=["Santé"], summary="Vérifie que l'API et la base répondent")
def health(db: DbSession) -> dict[str, str]:
    db.execute(text("SELECT 1"))
    return {"status": "ok"}
