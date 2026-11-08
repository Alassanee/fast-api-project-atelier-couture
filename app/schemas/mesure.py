"""Schémas Pydantic des prises de mesures.

RG2 : toutes les mesures sont facultatives, mais une prise en contient au moins
une ; chaque mesure est strictement positive et ne dépasse pas 300 cm.
"""

from datetime import date, datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.mesure import CHAMPS_MESURES

MESURE_MAX_CM = 300

Cm = Annotated[float | None, Field(gt=0, le=MESURE_MAX_CM, description="en cm")]


class _Valeurs(BaseModel):
    """Les 18 mesures facultatives, en centimètres."""

    taille_cm: Cm = None
    tour_cou: Cm = None
    carrure_dos: Cm = None
    longueur_epaule: Cm = None
    tour_poitrine: Cm = None
    tour_taille: Cm = None
    tour_bassin: Cm = None
    longueur_manche: Cm = None
    tour_bras: Cm = None
    tour_poignet: Cm = None
    longueur_dos: Cm = None
    longueur_haut: Cm = None
    longueur_pantalon: Cm = None
    tour_cuisse: Cm = None
    tour_genou: Cm = None
    bas_pantalon: Cm = None
    entrejambe: Cm = None
    longueur_robe: Cm = None


MESSAGE_AUCUNE_MESURE = "une prise de mesures doit contenir au moins une mesure"


def a_au_moins_une_mesure(objet: object) -> bool:
    return any(getattr(objet, champ) is not None for champ in CHAMPS_MESURES)


class MesureCreate(_Valeurs):
    date_prise: date | None = Field(default=None, description="Aujourd'hui par défaut")
    notes: str | None = None

    @model_validator(mode="after")
    def _au_moins_une(self) -> "MesureCreate":
        if not a_au_moins_une_mesure(self):
            raise ValueError(MESSAGE_AUCUNE_MESURE)
        return self


class MesureUpdate(_Valeurs):
    """PATCH : corrige une erreur de saisie ; une mesure peut être remise à null.
    Le contrôle « au moins une mesure » après correction est fait par le service."""

    date_prise: date | None = None
    notes: str | None = None

    @model_validator(mode="after")
    def _date_non_vide(self) -> "MesureUpdate":
        if "date_prise" in self.model_fields_set and self.date_prise is None:
            raise ValueError("le champ « date_prise » ne peut pas être vide")
        return self


class MesureRead(_Valeurs):
    model_config = ConfigDict(from_attributes=True)

    id: int
    client_id: int
    date_prise: date
    prise_par_id: int
    notes: str | None
    created_at: datetime
