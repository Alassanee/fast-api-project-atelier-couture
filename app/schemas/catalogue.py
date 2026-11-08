"""Schémas Pydantic du catalogue des prestations (TypeVetement)."""

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class TypeVetementCreate(BaseModel):
    nom: str = Field(min_length=1, max_length=100)
    description: str | None = None
    prix_base: int = Field(gt=0, description="Prix de base en FCFA")
    delai_jours: int = Field(ge=0, le=365, description="Délai de confection en jours")

    @field_validator("nom")
    @classmethod
    def _nom_non_vide(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("ne peut pas être vide")
        return v

    @field_validator("description")
    @classmethod
    def _description(cls, v: str | None) -> str | None:
        return (v.strip() or None) if v is not None else None


class TypeVetementUpdate(BaseModel):
    """PATCH : seuls les champs envoyés sont modifiés. actif=false retire la prestation."""

    nom: str | None = Field(default=None, max_length=100)
    description: str | None = None
    prix_base: int | None = Field(default=None, gt=0)
    delai_jours: int | None = Field(default=None, ge=0, le=365)
    actif: bool | None = None

    @model_validator(mode="after")
    def _pas_de_vide(self) -> "TypeVetementUpdate":
        for champ in ("nom", "prix_base", "delai_jours", "actif"):
            if champ in self.model_fields_set and getattr(self, champ) is None:
                raise ValueError(f"le champ « {champ} » ne peut pas être vide")
        if "nom" in self.model_fields_set:
            self.nom = self.nom.strip()
            if not self.nom:
                raise ValueError("le champ « nom » ne peut pas être vide")
        if "description" in self.model_fields_set and self.description is not None:
            self.description = self.description.strip() or None
        return self


class TypeVetementRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nom: str
    description: str | None
    prix_base: int
    delai_jours: int
    actif: bool
