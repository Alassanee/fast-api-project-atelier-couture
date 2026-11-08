"""Schémas Pydantic des clients : création, modification et lecture séparées.

La normalisation et la validation du téléphone (RG1) sont faites dans le service.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from app.enums import Genre
from app.schemas.commande import CommandeListe


def _nettoyer(v: str | None) -> str | None:
    return v.strip() if isinstance(v, str) else v


class ClientCreate(BaseModel):
    nom: str = Field(min_length=1, max_length=100)
    prenom: str = Field(min_length=1, max_length=100)
    telephone: str = Field(min_length=1, max_length=40)
    email: EmailStr | None = None
    adresse: str | None = Field(default=None, max_length=255)
    genre: Genre | None = None
    notes: str | None = None

    @field_validator("nom", "prenom", "telephone", mode="after")
    @classmethod
    def _non_vide(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("ne peut pas être vide")
        return v

    @field_validator("adresse", "notes", mode="after")
    @classmethod
    def _strip(cls, v: str | None) -> str | None:
        return _nettoyer(v) or None


class ClientUpdate(BaseModel):
    """PATCH : seuls les champs envoyés sont modifiés."""

    nom: str | None = Field(default=None, max_length=100)
    prenom: str | None = Field(default=None, max_length=100)
    telephone: str | None = Field(default=None, max_length=40)
    email: EmailStr | None = None
    adresse: str | None = Field(default=None, max_length=255)
    genre: Genre | None = None
    notes: str | None = None

    @model_validator(mode="after")
    def _champs_obligatoires_non_vides(self) -> "ClientUpdate":
        # nom, prenom et telephone ne peuvent pas être vidés (route 10).
        for champ in ("nom", "prenom", "telephone"):
            if champ in self.model_fields_set:
                valeur = _nettoyer(getattr(self, champ))
                if not valeur:
                    raise ValueError(f"le champ « {champ} » ne peut pas être vide")
                setattr(self, champ, valeur)
        for champ in ("adresse", "notes"):
            if champ in self.model_fields_set:
                setattr(self, champ, _nettoyer(getattr(self, champ)) or None)
        return self


class ClientRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nom: str
    prenom: str
    telephone: str
    email: str | None
    adresse: str | None
    genre: Genre | None
    notes: str | None
    created_at: datetime
    updated_at: datetime


class ClientResume(BaseModel):
    """Route 13 : synthèse du client, commandes annulées exclues."""

    nb_commandes: int
    chiffre_affaires: int
    total_paye: int
    solde_du: int
    derniere_commande: CommandeListe | None
    a_des_mesures: bool
