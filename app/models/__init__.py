"""Import de tous les modèles : nécessaire pour qu'Alembic les découvre."""

from app.models.client import Client
from app.models.commande import Commande, HistoriqueStatut, LigneCommande
from app.models.livraison import Livraison
from app.models.mesure import CHAMPS_MESURES, Mesure
from app.models.paiement import Paiement
from app.models.type_vetement import TypeVetement
from app.models.utilisateur import Utilisateur

__all__ = [
    "CHAMPS_MESURES",
    "Client",
    "Commande",
    "HistoriqueStatut",
    "LigneCommande",
    "Livraison",
    "Mesure",
    "Paiement",
    "TypeVetement",
    "Utilisateur",
]
