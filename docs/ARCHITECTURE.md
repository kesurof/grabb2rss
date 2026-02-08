# Architecture de Grabb2RSS (Mode Fusionne)

## Vue d'ensemble

Le backend utilise un pipeline unique d'ingestion des grabs:

1. Source temps reel: webhook Radarr/Sonarr (`/api/webhook/grab`)
2. Source de reconciliation: historique Radarr/Sonarr (sync cyclique + manuel)
3. Ingestion canonique: upsert idempotent en base (`instance + download_id`)
4. Exposition UI/API: `/grabs` (events unifies) et `/torrents` (fichiers)

Le pipeline est pilote par `history.ingestion_mode`:

- `webhook_only`: webhook actif, sync history desactivee.
- `webhook_plus_history`: webhook actif + sync history active.
- `history_only`: webhook ignore, sync history active.

## Composants principaux

- Entree application: `src/main.py`
- API/routes/pages: `src/api.py`, `src/auth_routes.py`, `src/setup_routes.py`
- Configuration: `src/config.py`, `src/settings_schema.py`
- Base de donnees/migrations: `src/db.py`
- Ingestion webhook grab: `src/webhook_grab.py`
- Reconciliation historique consolide: `src/history_reconcile.py`
- Integrations Prowlarr/Radarr/Sonarr: `src/prowlarr.py`, `src/radarr_sonarr.py`
- Gestion torrent: `src/torrent.py`
- Scheduler: `src/scheduler.py`
- UI: `web/templates/`, `web/static/`

## Flux backend officiel

1. Webhook Radarr/Sonarr envoie un event grab.
2. `src/webhook_grab.py` valide token, score/matching, hash et tente recuperation torrent.
3. Le grab est ingere via le modele canonique en DB.
4. Le scheduler lance periodiquement la sync de l'historique consolide.
5. `src/history_reconcile.py` lit l'historique apps configurees et upsert les grabs manquants/synchronises.
6. L'UI `/grabs` affiche la vue fusionnee; `/torrents` affiche les fichiers physiques.

## Parametres runtime (config/settings.yml)

### Bloc `history`

- `history.sync_interval_seconds`: intervalle du job de sync history (900..86400).
- `history.lookback_days`: fenetre de rattrapage history (1..30).
- `history.download_from_history`: autorise le telechargement `.torrent` pendant la sync history.
- `history.min_score`: score minimal de matching Prowlarr en mode history.
- `history.strict_hash`: exiger hash valide en mode history.
- `history.ingestion_mode`: mode global d'ingestion (`webhook_only|webhook_plus_history|history_only`).

### Bloc `sync` (maintenance)

- `sync.retention_hours`: retention locale des grabs en DB.
- `sync.auto_purge`: active/desactive la purge automatique.

## Pages UI cibles

- `/overview`: synthese
- `/grabs`: historique fusionne webhook + historique consolide
- `/torrents`: fichiers torrent
- `/rss-ui`: configuration RSS/API keys
- `/config`: configuration applicative
- `/security`: redirection vers `/config?tab=security`
- `/logs`: redirection vers `/config?tab=maintenance`

`/history-grabb` est maintenu en redirection vers `/grabs` pour compatibilite.

## Donnees et idempotence

La table `grabs` est la source canonique et inclut notamment:

- `instance`
- `download_id`
- `source_first_seen`
- `source_last_seen`
- `status`
- `last_error`
- `updated_at`

Contrainte cle: unicite logique `instance + download_id`.

## Scheduler

Le scheduler est recentre sur:

- Sync historique consolide cyclique
- Housekeeping (nettoyage, maintenance)

Le flux polling legacy Prowlarr n'est plus la source principale d'ingestion.

Comportement detaille:

- Job `sync_grab_history` cree seulement si `history_apps` configurees et `history.ingestion_mode != webhook_only`.
- `history.ingestion_mode=history_only` neutralise l'ingestion webhook.
- Housekeeping applique `sync.auto_purge` + `sync.retention_hours`.

## Endpoints API cle

- `POST /api/webhook/grab`
- `GET /api/grabs`
- `POST /api/grabs/recover`
- `GET /api/torrents`
- `GET /api/torrents/download/{filename}`
- `POST /api/history/reconcile/sync`
- `GET /api/history/reconcile`
- `POST /api/history/reconcile/recover`

## Depreciations supprimees

- Ancienne logique de collecte multiple non unifiee
- Actions UI legacy de comparaison ponctuelle non persistante
- Dependance au polling Prowlarr comme flux central
- Parametres supprimes: `sync.interval`, `sync.dedup_hours`, `prowlarr.history_page_size`
