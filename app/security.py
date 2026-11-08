"""Sécurité : hachage des mots de passe (Argon2, RG21) et jetons JWT (RG22)."""

from datetime import UTC, datetime, timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from app.config import settings

_hasher = PasswordHasher()

# Hash factice : vérifié quand l'e-mail est inconnu, pour que la réponse prenne
# le même temps que pour un mauvais mot de passe (RG23).
_HASH_FACTICE = _hasher.hash("mot-de-passe-factice")


def hacher_mot_de_passe(mot_de_passe: str) -> str:
    return _hasher.hash(mot_de_passe)


def verifier_mot_de_passe(mot_de_passe: str, mot_de_passe_hash: str | None) -> bool:
    try:
        return _hasher.verify(mot_de_passe_hash or _HASH_FACTICE, mot_de_passe)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def creer_jeton_acces(utilisateur_id: int) -> tuple[str, int]:
    """Crée un JWT signé avec date d'expiration. Renvoie (jeton, durée en secondes)."""
    duree = timedelta(minutes=settings.access_token_expire_minutes)
    maintenant = datetime.now(UTC)
    charge = {"sub": str(utilisateur_id), "iat": maintenant, "exp": maintenant + duree}
    jeton = jwt.encode(charge, settings.secret_key, algorithm=settings.jwt_algorithm)
    return jeton, int(duree.total_seconds())


def decoder_jeton(jeton: str) -> int | None:
    """Renvoie l'id de l'utilisateur, ou None si le jeton est invalide ou expiré."""
    try:
        charge = jwt.decode(
            jeton,
            settings.secret_key,
            algorithms=[settings.jwt_algorithm],
            options={"require": ["exp", "sub"]},
        )
        return int(charge["sub"])
    except (jwt.PyJWTError, ValueError, TypeError):
        return None
