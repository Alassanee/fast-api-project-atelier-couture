"""Valeurs autorisées (énumérations) utilisées par les modèles et les schémas."""

from enum import StrEnum


class Role(StrEnum):
    admin = "admin"
    tailleur = "tailleur"
    accueil = "accueil"


class Genre(StrEnum):
    homme = "homme"
    femme = "femme"
    enfant = "enfant"


class StatutCommande(StrEnum):
    en_attente = "en_attente"
    en_coupe = "en_coupe"
    en_couture = "en_couture"
    essayage = "essayage"
    retouches = "retouches"
    terminee = "terminee"
    livree = "livree"
    annulee = "annulee"


class ModePaiement(StrEnum):
    especes = "especes"
    wave = "wave"
    orange_money = "orange_money"
    virement = "virement"
    cheque = "cheque"


class ModeLivraison(StrEnum):
    retrait_atelier = "retrait_atelier"
    domicile = "domicile"


class StatutLivraison(StrEnum):
    planifiee = "planifiee"
    livree = "livree"
