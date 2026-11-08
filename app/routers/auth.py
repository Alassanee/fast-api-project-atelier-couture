"""Routes d'authentification (routes 1 et 2)."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from app.dependencies import DbSession, UtilisateurCourant
from app.schemas.auth import Token
from app.schemas.utilisateur import UtilisateurRead
from app.security import creer_jeton_acces
from app.services import auth as service

router = APIRouter(prefix="/auth", tags=["Authentification"])


@router.post("/login", response_model=Token, summary="Connexion (username = e-mail)")
def login(db: DbSession, form: Annotated[OAuth2PasswordRequestForm, Depends()]) -> Token:
    utilisateur = service.authentifier(db, form.username, form.password)
    if utilisateur is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=service.MESSAGE_ECHEC_CONNEXION,
            headers={"WWW-Authenticate": "Bearer"},
        )
    jeton, expires_in = creer_jeton_acces(utilisateur.id)
    return Token(access_token=jeton, expires_in=expires_in)


@router.get("/me", response_model=UtilisateurRead, summary="Profil de l'utilisateur connecté")
def me(utilisateur: UtilisateurCourant) -> UtilisateurRead:
    return UtilisateurRead.model_validate(utilisateur)
