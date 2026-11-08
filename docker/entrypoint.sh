#!/bin/sh
# Démarrage du conteneur API :
#   1. crée ou met à jour le schéma de la base (alembic upgrade head, jamais create_all) ;
#   2. lance le script d'initialisation (premier admin + catalogue, et comptes de
#      démonstration si SEED_DEMO=true), sans doublon si relancé ;
#   3. démarre l'API.
set -e

echo "==> Migrations Alembic"
alembic upgrade head

if [ "${RUN_SEED:-true}" = "true" ]; then
    echo "==> Initialisation (python -m app.seed)"
    if [ "${SEED_DEMO:-false}" = "true" ]; then
        python -m app.seed --demo
    else
        python -m app.seed
    fi
fi

echo "==> Démarrage de l'API"
exec "$@"
