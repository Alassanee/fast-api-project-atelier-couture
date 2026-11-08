# API de gestion d'un atelier de couture

Back-end REST d'un atelier de couture à Dakar : clients et historique de leurs mesures,
commandes et suivi de production, acomptes et soldes (espèces, Wave, Orange Money…),
livraisons, chiffre d'affaires, impayés et retards.

| Élément | Choix |
|---|---|
| Langage | Python **3.12.2** |
| Framework | FastAPI (Swagger sur `/docs`) |
| Base de données | PostgreSQL 16 |
| Accès aux données | SQLAlchemy 2 (`Mapped`, `mapped_column`, `select`) |
| Migrations | Alembic (`alembic upgrade head`, jamais `create_all`) |
| Validation | Pydantic 2 (schémas distincts création / modification / lecture) |
| Sécurité | JWT signé avec expiration, mots de passe hachés en Argon2 |
| Tests | pytest + `TestClient`, sur une base PostgreSQL dédiée |
| Conteneurs | `Dockerfile` + `docker-compose.yml` (API + PostgreSQL) |

Les versions exactes des bibliothèques sont dans [`requirements.txt`](requirements.txt).

---

## 1. Démarrage rapide avec Docker (recommandé)

Prérequis : Git et Docker Desktop (ou Docker Engine + Compose v2).

```bash
git clone https://github.com/Alassanee/fast-api-project-atelier-couture.git
cd fast-api-project-atelier-couture
cp .env.example .env
docker compose up --build
```

Au démarrage, le conteneur `api` :

1. applique les migrations (`alembic upgrade head`) ;
2. lance le script d'initialisation (`python -m app.seed`) : premier administrateur,
   catalogue de l'annexe B et, si `SEED_DEMO=true`, les comptes accueil et tailleur ;
3. démarre l'API.

L'API est alors disponible sur :

- Swagger : <http://localhost:8000/docs>
- Santé : <http://localhost:8000/health> → `{"status": "ok"}`

> Avant une utilisation réelle, remplacez dans `.env` les valeurs `changer_moi…`,
> en particulier `SECRET_KEY` :
> `python -c "import secrets; print(secrets.token_hex(32))"`.

Arrêter : `docker compose down`. Tout effacer, base comprise : `docker compose down -v`.

---

## 2. Installation en local (développement)

Prérequis : Python 3.12.2 et Docker (pour PostgreSQL).

```bash
git clone https://github.com/Alassanee/fast-api-project-atelier-couture.git
cd fast-api-project-atelier-couture
cp .env.example .env

python3.12 -m venv .venv
source .venv/bin/activate          # Windows : .venv\Scripts\activate
pip install -r requirements.txt

docker compose up -d db            # PostgreSQL seul, sur localhost:5432
alembic upgrade head               # crée le schéma
python -m app.seed --demo          # admin + catalogue + comptes de démonstration
uvicorn app.main:app --reload      # http://127.0.0.1:8000/docs
```

Si l'API Docker tourne déjà sur le port 8000, arrêtez-la d'abord : `docker compose stop api`.

### Variables d'environnement

Toute la configuration vient du fichier `.env`, qui n'est jamais commité. Modèle :
[`.env.example`](.env.example).

| Variable | Rôle |
|---|---|
| `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, `POSTGRES_PORT` | Base PostgreSQL (conteneur `db`) |
| `DATABASE_URL` | Connexion de l'API (en Docker, l'hôte `db` est imposé par `docker-compose.yml`) |
| `TEST_DATABASE_URL` | Base utilisée par pytest (créée automatiquement) |
| `SECRET_KEY`, `JWT_ALGORITHM`, `ACCESS_TOKEN_EXPIRE_MINUTES` | Signature et durée des jetons JWT |
| `ADMIN_EMAIL`, `ADMIN_PASSWORD`, `ADMIN_NOM_COMPLET` | Premier administrateur créé par le seed |
| `DEMO_PASSWORD` | Mot de passe des comptes de démonstration (`--demo`) |
| `API_PORT`, `RUN_SEED`, `SEED_DEMO` | Port publié, seed au démarrage, comptes de démo au démarrage |

---

## 3. Comptes de test

Avec le `.env` copié depuis `.env.example` :

| Rôle | E-mail | Mot de passe | Créé par |
|---|---|---|---|
| admin | `admin@atelier.sn` | `changer_moi_123` | `python -m app.seed` |
| accueil | `accueil@atelier.sn` | `changer_moi_demo` | `python -m app.seed --demo` (ou `SEED_DEMO=true`) |
| tailleur | `tailleur@atelier.sn` | `changer_moi_demo` | `python -m app.seed --demo` (ou `SEED_DEMO=true`) |

Si vous avez modifié `ADMIN_PASSWORD` ou `DEMO_PASSWORD`, utilisez vos valeurs.

**Se connecter dans Swagger** : bouton **Authorize**, puis saisir l'e-mail dans `username`
et le mot de passe dans `password`. La route `POST /api/v1/auth/login` renvoie
`access_token`, `token_type` et `expires_in`.

---

## 4. Lancer les tests

PostgreSQL doit tourner (`docker compose up -d db`), puis, dans l'environnement virtuel :

```bash
pytest
```

- La base `TEST_DATABASE_URL` (`atelier_couture_test`) est créée si besoin. Son schéma
  est construit par les **migrations Alembic**, ce qui teste aussi la migration.
- Les tables sont vidées après chaque test : la base de travail n'est jamais touchée.
- 264 tests : au moins un test par règle de gestion (RG1 à RG24), les droits de chaque rôle
  sur chaque domaine (401 / 403), et le **scénario de démonstration complet de l'annexe A**
  ([`tests/test_scenario_demo.py`](tests/test_scenario_demo.py)).

---

## 5. Architecture

```
app/
  main.py          application FastAPI, inclusion des routeurs, /health
  config.py        paramètres lus depuis l'environnement (.env)
  database.py      moteur SQLAlchemy, session, Base
  security.py      Argon2 et JWT
  dependencies.py  utilisateur connecté (401) et contrôle des rôles (403)
  exceptions.py    erreurs métier → {"detail": "..."} (404 / 409 / 422), messages en français
  enums.py         rôles, statuts, modes de paiement et de livraison
  models/          modèles SQLAlchemy (9 tables de l'énoncé)
  schemas/         schémas Pydantic Create / Update / Read
  services/        toute la logique métier (règles RG1 à RG24)
  routers/         un routeur par domaine : droits → service → commit
  seed.py          python -m app.seed [--demo]
alembic/           migrations (schéma initial complet)
docker/            script de démarrage du conteneur
tests/             tests pytest
```

**Règles d'architecture**

- Les **routeurs** vérifient les droits, appellent un service, puis valident la transaction.
  Ils ne contiennent aucune règle de gestion.
- Les **services** contiennent les calculs (montants, solde), les transitions de statuts et
  les règles de livraison. Ils lèvent des erreurs métier (`NonTrouve`, `Conflit`,
  `DonneesInvalides`, `Interdit`).
- Les **modèles** ne sont jamais renvoyés tels quels : chaque réponse passe par un schéma de
  lecture, et le hash du mot de passe n'est jamais exposé.

**Conventions**

- Toutes les routes sont préfixées par `/api/v1`, sauf `/health`.
- Les erreurs ont la forme `{"detail": "message en français"}`, y compris les erreurs de
  validation.
- Les listes paginées ont la forme `{"items": [...], "total": n, "limit": n, "offset": n}`
  (`limit` vaut 20 par défaut, 100 au maximum).
- Les PATCH ne modifient que les champs envoyés.

---

## 6. Routes réalisées (44 sur 44)

Rôles : **Tous** = tout utilisateur connecté. L'admin a accès à tout.

### Palier 1 : socle

| N° | Méthode | Chemin | Rôle |
|---|---|---|---|
| 1 | POST | `/auth/login` | Public |
| 2 | GET | `/auth/me` | Connecté |
| 3 | POST | `/utilisateurs` | Admin |
| 4 | GET | `/utilisateurs` | Admin |
| 5 | GET | `/utilisateurs/{id}` | Admin |
| 6 | PATCH | `/utilisateurs/{id}` | Admin |
| 7 | POST | `/clients` | Tous |
| 8 | GET | `/clients` (`q`, `genre`, `limit`, `offset`) | Tous |
| 9 | GET | `/clients/{id}` | Tous |
| 10 | PATCH | `/clients/{id}` | Tous |
| 11 | DELETE | `/clients/{id}` | Admin |
| 12 | GET | `/clients/{id}/commandes` | Tous |
| 13 | GET | `/clients/{id}/resume` | Tous |
| 14 | POST | `/catalogue` | Admin |
| 15 | GET | `/catalogue` (`actifs_seulement`) | Tous |
| 16 | GET | `/catalogue/{id}` | Tous |
| 17 | PATCH | `/catalogue/{id}` | Admin |

### Palier 2 : cœur métier

| N° | Méthode | Chemin | Rôle |
|---|---|---|---|
| 18 | POST | `/clients/{id}/mesures` | Tailleur |
| 19 | GET | `/clients/{id}/mesures` | Tous |
| 20 | GET | `/clients/{id}/mesures/derniere` | Tous |
| 21 | GET | `/mesures/{id}` | Tous |
| 22 | PATCH | `/mesures/{id}` | Tailleur |
| 23 | DELETE | `/mesures/{id}` | Tailleur |
| 24 | POST | `/commandes` | Accueil |
| 25 | GET | `/commandes` (`statut`, `client_id`, `en_retard`, `date_min`, `date_max`, `numero`) | Tous |
| 26 | GET | `/commandes/{id}` | Tous |
| 27 | PATCH | `/commandes/{id}` | Accueil |
| 28 | POST | `/commandes/{id}/statut` | Tous (le tailleur ne peut pas annuler) |
| 29 | GET | `/commandes/{id}/historique` | Tous |
| 30 | POST | `/commandes/{id}/lignes` | Accueil |
| 31 | DELETE | `/commandes/{id}/lignes/{ligne_id}` | Accueil |
| 32 | POST | `/commandes/{id}/paiements` | Accueil |
| 33 | GET | `/commandes/{id}/paiements` | Tous |
| 34 | DELETE | `/paiements/{id}` | Admin |

### Palier 3 : finalisation

| N° | Méthode | Chemin | Rôle |
|---|---|---|---|
| 35 | PUT | `/commandes/{id}/livraison` | Accueil |
| 36 | GET | `/commandes/{id}/livraison` | Tous |
| 37 | POST | `/commandes/{id}/livraison/confirmer` | Accueil |
| 38 | GET | `/livraisons` (`statut`, `date_min`, `date_max`) | Tous |
| 39 | GET | `/statistiques/tableau-de-bord` | Admin |
| 40 | GET | `/statistiques/chiffre-affaires` (`granularite`, `date_debut`, `date_fin`) | Admin |
| 41 | GET | `/statistiques/types-vetement` (`date_debut`, `date_fin`) | Admin |
| 42 | GET | `/statistiques/top-clients` (`date_debut`, `date_fin`, `limite`) | Admin |
| 43 | GET | `/statistiques/impayes` (`limit`, `offset`) | Admin |
| 44 | GET | `/health` (hors préfixe) | Public |

---

## 7. Règles de gestion : où elles sont appliquées

| Règles | Service |
|---|---|
| RG1 (téléphone normalisé et unique), RG4 (suppression d'un client) | [`services/clients.py`](app/services/clients.py) |
| RG2, RG3, RG4 (mesures) | [`services/mesures.py`](app/services/mesures.py), [`schemas/mesure.py`](app/schemas/mesure.py) |
| RG5 à RG15 (numéro, montants, dates, mesures, lignes, retard, workflow, historique) | [`services/commandes.py`](app/services/commandes.py) |
| RG16, RG17 (paiements) | [`services/paiements.py`](app/services/paiements.py) |
| RG18 à RG20 (livraisons) | [`services/livraisons.py`](app/services/livraisons.py) |
| RG21 à RG23 (mots de passe, JWT, connexion) | [`security.py`](app/security.py), [`dependencies.py`](app/dependencies.py), [`services/auth.py`](app/services/auth.py) |
| RG24 (l'admin ne peut pas se désactiver ni se retirer son rôle) | [`services/utilisateurs.py`](app/services/utilisateurs.py) |
| Statistiques | [`services/statistiques.py`](app/services/statistiques.py) |

---

## 8. Choix d'interprétation

Points où l'énoncé laissait une marge, et le choix retenu :

- **Connexion** : par **e-mail** (`username` = e-mail), comme l'indiquent le modèle
  `Utilisateur`, la route 1 et RG23. L'e-mail ne tient pas compte de la casse.
- **Référence inconnue dans un corps** (client, prestation, mesure) : 404.
- **`derniere_commande`** (route 13) : la commande complète (numéro, date, statut, solde…),
  ou `null` si le client n'a pas de commande.
- **Route 38** : liste simple, car l'énoncé ne la dit pas paginée. Les livraisons de
  commandes annulées sont exclues de la tournée.
- **Tableau de bord** : `commandes_pretes_a_livrer` (statut `terminee`) et
  `livraisons_du_jour` sont des listes détaillées. Les compteurs sont préfixés `nb_`.
  `nb_commandes_mois` exclut les commandes annulées, comme le chiffre d'affaires.
- **Encaissé** : tous les paiements reçus sur la période, y compris ceux d'une commande
  annulée ensuite (l'argent a bien été reçu).
- **Livraison** : une date effective future, ou antérieure à la commande, est refusée (422).
- **Paiement** : la commande est verrouillée pendant l'encaissement (`SELECT … FOR UPDATE`).
  Deux paiements simultanés ne peuvent donc pas dépasser le solde.
- **Comptes de démonstration** : `python -m app.seed --demo` crée un compte accueil et un compte
  tailleur, en plus de l'admin et du catalogue demandés, pour dérouler l'annexe A.
