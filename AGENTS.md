# Plan de développement — YAZIO MCP

## Mission

Construire en Python un serveur MCP non officiel et maintenable pour l’API
privée YAZIO v22, sans reprendre l’ancien package npm `yazio` limité à la v15.

Le projet utilise Python 3.10+, `uv`, FastMCP 4 avec Streamable HTTP,
`httpx.AsyncClient`, Pydantic v2, pytest, respx, Ruff et mypy.

Référence communautaire :
<https://github.com/yazio-community/yazio-api-specification>.

## Règles impératives

- YAZIO ne fournit aucune API publique : ne jamais présenter les routes ou
  schémas observés comme un contrat stable.
- Ne jamais écrire sur un compte YAZIO réel sans annoncer précisément
  l’opération et obtenir l’accord explicite de l’utilisateur.
- Les validations initiales sont locales ou en lecture seule.
- Les tests standards ne doivent jamais toucher un compte réel.
- Ne jamais journaliser identifiants, mots de passe, tokens OAuth, en-têtes
  d’authentification ou données de santé.
- Ne pas inventer une route, un payload ou une sémantique. Toute observation
  doit devenir une fixture sanitisée et un test.
- Conserver la couche FastMCP fine, sans logique d’accès à YAZIO.
- Ne pas réinitialiser Git ou `uv` et préserver les changements existants.
- Ne pas ajouter d’abstraction sans cas d’usage ou test qui la justifie.

## Architecture cible

```text
Client MCP
    ↓ Streamable HTTP
FastMCP
    ↓
Services métier
    ↓
YazioGateway (Protocol)
    ↓
YazioHttpClient (httpx.AsyncClient)
    ↓ HTTPS / JSON
API privée YAZIO v22
```

Structure cible :

```text
src/yazio_mcp/
├── __init__.py
├── server.py
├── config.py
├── errors.py
├── models/
│   ├── __init__.py
│   ├── auth.py
│   ├── diary.py
│   ├── products.py
│   └── user.py
├── ports/
│   ├── __init__.py
│   └── yazio_gateway.py
├── adapters/
│   ├── __init__.py
│   └── yazio_http.py
└── services/
    ├── __init__.py
    └── diary.py

tests/
├── unit/
├── integration/
└── fixtures/
```

`YazioGateway` doit être un `typing.Protocol` asynchrone. Les modèles de
réponse Pydantic doivent utiliser `ConfigDict(extra="allow")`.

## État d’avancement

### Phase 1 — Socle local : terminée

- Package et distribution nommés `yazio_mcp`.
- Point d’entrée `yazio-mcp = "yazio_mcp.server:main"`.
- FastMCP servi en Streamable HTTP sur `127.0.0.1:8000/mcp` par défaut.
- Hôte, port et chemin configurables par arguments CLI.
- Route `GET /health` et outil MCP `health_check`, sans appel à YAZIO.
- Tests locaux, Ruff, mypy et fichier `uv.lock` opérationnels.

### Phase 2 — Configuration et modèles : terminée

- Configuration YAZIO chargée par `pydantic-settings`, avec secrets masqués.
- URL v22 et timeouts HTTP configurables et validés localement.
- Modèles d’authentification, utilisateur, produits et journal tolérants aux
  champs inconnus.
- Catégories `products`, `simple_products` et `recipe_portions` distinctes.
- Dates et heures connues normalisées par la validation des réponses.
- Fixtures sanitisées et tests locaux, sans appel réseau.

### Phase 3 — Port, adaptateur et authentification : terminée

- Port asynchrone `YazioGateway` défini pour les cinq lectures déjà observées.
- `YazioHttpClient` fondé sur un `httpx.AsyncClient` partagé et fermable.
- Authentification JSON sur `oauth/token`, relativement à la base v22.
- Token conservé en mémoire avec expiration et verrou anti-concurrence.
- Refresh token utilisé lorsqu’il existe, avec réauthentification de secours.
- `User-Agent` centralisé et erreurs applicatives stables, dont
  `version_blocked`.
- Service de journal testé avec un faux gateway, sans HTTP.
- Authentification, expiration, refresh et erreurs couverts par `respx`.

## Plan restant

### Phase 4 — Lecture seule

Confirmer les routes et payloads avec la spécification communautaire ou des
captures sanitisées, puis implémenter :

- `get_user` ;
- `get_user_daily_summary` ;
- `get_user_consumed_items` ;
- `search_products` ;
- `get_product`.

Pour chaque opération : modèle, méthode du port, adaptateur, service si utile,
outil MCP fin et tests des réponses nominales, partielles et erronées.

Critère de sortie : cinq outils fonctionnels sur fixtures ; tests réels
explicitement activés et strictement en lecture seule.

### Phase 5 — Écriture contrôlée

Implémenter après confirmation des payloads :

- `add_consumed_product` ;
- `add_manual_food_entry` ;
- `delete_consumed_item`.

Utiliser des types différents pour les produits YAZIO et les entrées manuelles.
Tester les requêtes avec respx avant toute proposition de validation réelle.

Critère de sortie : trois opérations couvertes localement ; toute écriture
réelle exige une annonce et une autorisation explicites.

### Phase 6 — Intégration et documentation

- Marquer les tests réels avec `pytest -m live` et les ignorer par défaut.
- Exiger une activation supplémentaire et distincte pour l’écriture.
- Documenter MCP Inspector, la configuration et `version_blocked`.
- Ajouter une CI sans secrets qui exécute pytest, Ruff et mypy.
- Documenter la mise à jour des observations de l’API privée.

Critère de sortie : installation, lancement, test et diagnostic documentés.

## MVP fonctionnel visé

| Outil | Nature | Rôle |
|---|---|---|
| `health_check` | Locale | Vérifier le processus MCP |
| `get_user` | Lecture | Obtenir le profil utilisateur |
| `get_user_daily_summary` | Lecture | Lire le résumé nutritionnel quotidien |
| `get_user_consumed_items` | Lecture | Lire les trois catégories du journal |
| `search_products` | Lecture | Rechercher un produit YAZIO |
| `get_product` | Lecture | Lire les détails d’un produit |
| `add_consumed_product` | Écriture | Ajouter un produit YAZIO au journal |
| `add_manual_food_entry` | Écriture | Ajouter une entrée manuelle |
| `delete_consumed_item` | Destructive | Supprimer une entrée par identifiant |

La modification d’une entrée reste hors MVP jusqu’à déterminer si YAZIO
utilise une route dédiée, une réécriture avec le même identifiant ou une
suppression suivie d’une création.

## Configuration YAZIO prévue

```dotenv
YAZIO_USERNAME=
YAZIO_PASSWORD=
YAZIO_API_BASE_URL=https://yzapi.yazio.com/v22
YAZIO_USER_AGENT=
YAZIO_CONNECT_TIMEOUT_SECONDS=
YAZIO_READ_TIMEOUT_SECONDS=
```

Un futur `.env.example` peut documenter ces noms, mais `.env` doit rester
ignoré. URL, User-Agent, timeouts et identifiants viennent de la configuration.

## Stratégie de tests

- `tests/unit/` : modèles, services, configuration et faux gateway.
- `tests/integration/` : adaptateur HTTP simulé avec respx et serveur MCP.
- `tests/fixtures/` : réponses JSON sanitisées sans données personnelles.
- `pytest -m live` : tests réels optionnels, ignorés par défaut.

Commandes obligatoires avant de terminer une phase :

```bash
uv run pytest
uv run ruff check .
uv run mypy src tests
uv lock --check
```

## Points à confirmer par observation

- Routes, paramètres et schémas v22 exacts.
- Unités de l’énergie et des macronutriments.
- Sémantique de `date` et gestion du fuseau horaire.
- Format et durée de vie des tokens, disponibilité du refresh token.
- Pagination et localisation de la recherche.
- Mécanisme de modification d’une entrée.

Chaque réponse YAZIO utilisée pour les tests doit être sanitisée avant son
ajout au dépôt.
