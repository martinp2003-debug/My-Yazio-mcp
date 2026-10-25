# YAZIO MCP

Serveur MCP non officiel en Python pour explorer les données YAZIO via son
API privée v22.

> [!WARNING]
> YAZIO ne fournit pas d’API publique. Les routes utilisées ici peuvent changer
> sans préavis. Aucune écriture sur un compte réel ne doit être effectuée sans
> accord explicite de l’utilisateur.

## État actuel

La phase 1 est terminée :

- serveur FastMCP 4 en Streamable HTTP ;
- endpoint MCP `http://127.0.0.1:8000/mcp` ;
- route HTTP `GET /health` et outil MCP `health_check` ;
- tests locaux avec pytest ;
- contrôles Ruff et mypy ;
- aucun appel à YAZIO pour les contrôles de santé.

Le plan détaillé et les règles de contribution se trouvent dans
[AGENTS.md](AGENTS.md).

## Architecture

```mermaid
flowchart LR
    A[Client MCP<br/>Inspector] -->|Streamable HTTP| B[FastMCP<br/>server.py]
    B --> C[Services métier]
    C --> D[YazioGateway<br/>Protocol]
    D --> E[YazioHttpClient<br/>httpx.AsyncClient]
    E -->|HTTPS / JSON| F[API privée<br/>YAZIO v22]
    G[Configuration<br/>Pydantic Settings] --> B
    G --> E

    classDef client fill:#2563eb,stroke:#1d4ed8,color:#ffffff,stroke-width:2px;
    classDef server fill:#7c3aed,stroke:#6d28d9,color:#ffffff,stroke-width:2px;
    classDef domain fill:#0891b2,stroke:#0e7490,color:#ffffff,stroke-width:2px;
    classDef port fill:#059669,stroke:#047857,color:#ffffff,stroke-width:2px;
    classDef adapter fill:#ea580c,stroke:#c2410c,color:#ffffff,stroke-width:2px;
    classDef external fill:#dc2626,stroke:#b91c1c,color:#ffffff,stroke-width:2px;
    classDef config fill:#475569,stroke:#334155,color:#ffffff,stroke-width:2px;

    class A client;
    class B server;
    class C domain;
    class D port;
    class E adapter;
    class F external;
    class G config;
```

Seule la couche FastMCP et les contrôles de santé sont implémentés pour le
moment. Les autres blocs représentent l’architecture cible.

## Installation et lancement

Prérequis : Python 3.10 ou plus récent et
[`uv`](https://docs.astral.sh/uv/).

```bash
uv sync --dev
uv run yazio-mcp
```

Options réseau :

```bash
uv run yazio-mcp --host 127.0.0.1 --port 8080 --path /mcp
```

Vérification locale :

```bash
curl http://127.0.0.1:8000/health
```

Réponse attendue :

```json
{"status":"ok","service":"yazio-mcp"}
```

## Qualité

```bash
uv run pytest
uv run ruff check .
uv run mypy src tests
```

Référence communautaire :
[yazio-api-specification](https://github.com/yazio-community/yazio-api-specification).
