<div align="center">
  <img src="web/static/medias/logo-grabb2rss.webp" alt="Grabb2RSS" width="220">
  <h1>Grabb2RSS</h1>
  <p>Pipeline Grab -> Torrent -> RSS pour Radarr/Sonarr/Prowlarr.</p>
  <p><strong>Version</strong> : v3.0.1</p>
</div>

[![Docker](https://img.shields.io/badge/docker-ghcr.io-blue)](https://ghcr.io/kesurof/grabb2rss)
[![Python](https://img.shields.io/badge/python-3.11+-green)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-lightgrey)](LICENSE)

Grabb2RSS centralise les grabs de vos instances Arr, récupère les `.torrent` exploitables, et publie des flux RSS/JSON propres pour vos clients torrent.

## Ce que fait le projet

- Ingestion rapide via webhook grab (temps réel).
- Consolidation history cyclique (rattrapage contrôlé).
- Stockage unifié en base SQLite (grabs + fichiers).
- Publication RSS globale et par tracker.
- Interface web complète: overview, grabs, torrents, RSS, configuration.

## Avantages clés

- **Fiabilité**: mode `webhook + history` pour limiter les pertes en charge.
- **Cohérence**: vue métier unique sur `/grabs`, vue fichiers sur `/torrents`.
- **Sécurité**: authentification, sessions, API keys, webhook token.
- **Exploitation Docker**: defaults prêts pour réseau inter-containers.
- **Pilotage simple**: tous les réglages essentiels dans `/config`.

## Architecture opérationnelle

1. Radarr/Sonarr envoient `Grab` vers `/api/webhook/grab?token=...`.
2. Grabb2RSS tente la récupération `.torrent` via Prowlarr.
3. La consolidation history complète les manquants à intervalle défini.
4. Les données sont stockées en base, puis exposées via UI et flux RSS.

## Installation rapide (Docker)

```yaml
services:
  grabb2rss:
    image: ghcr.io/kesurof/grabb2rss:latest
    container_name: grabb2rss
    ports:
      - "8000:8000"
    volumes:
      - ./config:/config
      - ./data:/app/data
    environment:
      - TZ=Europe/Paris
    restart: unless-stopped
```

```bash
docker compose up -d
```

Ensuite: ouvrez `http://localhost:8000/setup` et suivez le wizard.

## Configuration recommandée

### Endpoints Docker (wizard)
- `http://prowlarr:9696`
- `http://radarr:7878`
- `http://sonarr:8989`

### Webhook Radarr/Sonarr
- URL recommandée: `http://grabb2rss:8000/api/webhook/grab?token=<token>`
- Fallback si résolution DNS impossible: `http://172.17.0.1:8000/api/webhook/grab?token=<token>`
- Trigger: `On Grab`

### Réglages clés
- `history.sync_interval_seconds`: intervalle consolidation (ex: `7200`)
- `history.lookback_days`: fenêtre de rattrapage (ex: `7`, borne `1..30`)
- `history.ingestion_mode`: `webhook_only` | `webhook_plus_history` | `history_only`
- `sync.retention_hours`: rétention locale (ex: `168`)
- `sync.auto_purge`: purge automatique (`true`/`false`)
- `webhook.min_score`: seuil de matching (ex: `3`)

## Utilisation

- UI: `/overview`, `/grabs`, `/torrents`, `/rss-ui`, `/config`
- Flux RSS global: `/rss`
- Flux RSS tracker: `/rss/tracker/{tracker}`
- Flux JSON: `/rss/torrent.json`

Authentification RSS/API:
- Header `X-API-Key: <key>`
- ou `Authorization: Bearer <key>`
- ou query `?apikey=<key>`

## Endpoints utiles

- `GET /health`
- `GET /api/stats`
- `GET /api/grabs`
- `POST /api/history/reconcile/sync`
- `POST /api/history/reconcile/recover`
- `GET /api/rss/urls`
- `GET /api/config`, `POST /api/config`

## Dossiers importants

- `src/` backend API + logique métier
- `web/templates/` pages UI
- `web/static/` JS/CSS
- `config/settings.yml` configuration active
- `config/settings-example.yml` base de référence
- `docs/` architecture et plans techniques
