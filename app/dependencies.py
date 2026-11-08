"""Dépendances communes : session, utilisateur connecté et contrôle des rôles."""

from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.enums import Role
from app.models import Utilisateur
from app.security import decoder_jeton

# auto_error=False : on renvoie nous-mêmes un 401 avec un message en français.
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"{settings.api_prefix}/auth/login", auto_error=False
)

DbSession = Annotated[Session, Depends(get_db)]


def _non_authentifie(message: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=message,
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user(
    db: DbSession, jeton: Annotated[str | None, Depends(oauth2_scheme)]
) -> Utilisateur:
    """Utilisateur du jeton. 401 si jeton absent, invalide, expiré ou compte désactivé."""
    if not jeton:
        raise _non_authentifie("Authentification requise : jeton d'accès manquant.")
    utilisateur_id = decoder_jeton(jeton)
    if utilisateur_id is None:
        raise _non_authentifie("Jeton d'accès invalide ou expiré.")
    # Rechargé depuis la base à chaque requête : un compte désactivé est
    # refusé immédiatement, même avec un jeton encore valide (RG22).
    utilisateur = db.get(Utilisateur, utilisateur_id)
    if utilisateur is None or not utilisateur.actif:
        raise _non_authentifie("Compte inexistant ou désactivé.")
    return utilisateur


UtilisateurCourant = Annotated[Utilisateur, Depends(get_current_user)]


def require_roles(*roles: Role) -> Callable[[Utilisateur], Utilisateur]:
    """Autorise les rôles donnés. L'administrateur est toujours autorisé (section 4)."""
    autorises = {Role.admin, *roles}

    def verifier(utilisateur: UtilisateurCourant) -> Utilisateur:
        if utilisateur.role not in autorises:
            noms = ", ".join(sorted(r.value for r in autorises))
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Action non autorisée pour le rôle « {utilisateur.role.value} ». "
                f"Rôle(s) requis : {noms}.",
            )
        return utilisateur

    return verifier


# Raccourcis utilisables dans les routeurs.
AdminSeulement = Annotated[Utilisateur, Depends(require_roles(Role.admin))]
Accueil = Annotated[Utilisateur, Depends(require_roles(Role.accueil))]
Tailleur = Annotated[Utilisateur, Depends(require_roles(Role.tailleur))]
