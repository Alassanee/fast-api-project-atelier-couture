"""Schémas Pydantic des utilisateurs : création, modification et lecture séparées."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from app.enums import Role

MOT_DE_PASSE_MIN = 8  # RG21


class UtilisateurCreate(BaseModel):
    email: EmailStr
    nom_complet: str = Field(min_length=1, max_length=150)
    mot_de_passe: str = Field(min_length=MOT_DE_PASSE_MIN, max_length=128)
    role: Role

    @field_validator("email")
    @classmethod
    def _email_minuscule(cls, v: str) -> str:
        return v.lower()

    @field_validator("nom_complet")
    @classmethod
    def _nom_non_vide(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("ne peut pas être vide")
        return v


class UtilisateurUpdate(BaseModel):
    """PATCH : seuls les champs envoyés sont modifiés."""

    nom_complet: str | None = Field(default=None, min_length=1, max_length=150)
    role: Role | None = None
    actif: bool | None = None
    mot_de_passe: str | None = Field(default=None, min_length=MOT_DE_PASSE_MIN, max_length=128)

    @model_validator(mode="after")
    def _pas_de_null(self) -> "UtilisateurUpdate":
        # Un champ envoyé explicitement à null ne peut pas vider une valeur obligatoire.
        for champ in self.model_fields_set:
            if getattr(self, champ) is None:
                raise ValueError(f"le champ « {champ} » ne peut pas être vide")
        if self.nom_complet is not None and not self.nom_complet.strip():
            raise ValueError("le champ « nom_complet » ne peut pas être vide")
        return self


class UtilisateurRead(BaseModel):
    """Lecture : aucune donnée sensible (jamais le hash du mot de passe)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    nom_complet: str
    role: Role
    actif: bool
    created_at: datetime
