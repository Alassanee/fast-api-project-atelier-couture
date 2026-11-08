"""Erreurs métier levées par les services, et leur conversion en réponses HTTP.

Toutes les erreurs ont la forme {"detail": "message en français"} (section 8).
"""

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class ErreurMetier(Exception):
    """Erreur de règle de gestion. Les services la lèvent, l'API la convertit."""

    status_code = status.HTTP_400_BAD_REQUEST

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


class NonTrouve(ErreurMetier):
    status_code = status.HTTP_404_NOT_FOUND


class Conflit(ErreurMetier):
    status_code = status.HTTP_409_CONFLICT


class DonneesInvalides(ErreurMetier):
    status_code = status.HTTP_422_UNPROCESSABLE_CONTENT


class Interdit(ErreurMetier):
    status_code = status.HTTP_403_FORBIDDEN


# --- Traduction des erreurs de validation Pydantic ---------------------------

_MESSAGES = {
    "missing": "champ obligatoire",
    "string_too_short": "doit contenir au moins {min_length} caractère(s)",
    "string_too_long": "doit contenir au plus {max_length} caractère(s)",
    "greater_than": "doit être strictement supérieur à {gt}",
    "greater_than_equal": "doit être supérieur ou égal à {ge}",
    "less_than": "doit être strictement inférieur à {lt}",
    "less_than_equal": "doit être inférieur ou égal à {le}",
    "int_parsing": "doit être un nombre entier",
    "int_type": "doit être un nombre entier",
    "int_from_float": "doit être un nombre entier",
    "float_parsing": "doit être un nombre",
    "float_type": "doit être un nombre",
    "bool_parsing": "doit être vrai ou faux",
    "date_parsing": "doit être une date au format AAAA-MM-JJ",
    "date_from_datetime_parsing": "doit être une date au format AAAA-MM-JJ",
    "enum": "valeur invalide, valeurs possibles : {expected}",
    "literal_error": "valeur invalide, valeurs possibles : {expected}",
    "string_type": "doit être une chaîne de caractères",
    "list_type": "doit être une liste",
    "too_short": "doit contenir au moins {min_length} élément(s)",
    "extra_forbidden": "champ non autorisé",
    "json_invalid": "JSON invalide",
    "model_attributes_type": "objet attendu",
    "dict_type": "objet attendu",
}


def _message_erreur(err: dict) -> str:
    champ = ".".join(str(p) for p in err.get("loc", ()) if p not in ("body", "query", "path"))
    type_ = err.get("type", "")
    ctx = err.get("ctx") or {}
    if type_ == "value_error":
        # Message écrit par nos validateurs (déjà en français).
        texte = str(ctx.get("error", err.get("msg", "")))
    elif type_ in _MESSAGES:
        try:
            texte = _MESSAGES[type_].format(**ctx)
        except (KeyError, IndexError):
            texte = _MESSAGES[type_]
    else:
        texte = err.get("msg", "valeur invalide")
    return f"{champ} : {texte}" if champ else texte


def installer_gestionnaires(app: FastAPI) -> None:
    @app.exception_handler(ErreurMetier)
    async def _erreur_metier(_: Request, exc: ErreurMetier) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

    @app.exception_handler(RequestValidationError)
    async def _erreur_validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        messages = [_message_erreur(e) for e in exc.errors()]
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content={"detail": "Données invalides : " + " ; ".join(messages)},
        )
