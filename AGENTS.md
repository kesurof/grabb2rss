# Directives de Répertoire

## Vue d’ensemble du projet
Grabb2RSS transforme les grabs Radarr/Sonarr/Prowlarr en flux RSS et fichiers `.torrent` exploitables. L’architecture repose sur FastAPI (`src/api.py`), une logique métier modulaire (`src/*.py`), une UI serveur Jinja2 (`web/templates`) et un scheduler (`src/scheduler.py`). Le projet suit un modèle “backend centré”: la UI consomme exclusivement les endpoints internes `/api/*`.

## Structure du projet
- `src/main.py`: point d’entrée.
- `src/api.py`: routes HTTP principales, pages web, middleware.
- `src/auth_routes.py`, `src/setup_routes.py`: routes spécialisées.
- `src/prowlarr.py`, `src/radarr_sonarr.py`, `src/webhook_grab.py`, `src/history_reconcile.py`: ingestion et récupération.
- `src/db.py`: accès SQLite, schémas et utilitaires DB.
- `web/templates/pages/*`: pages (`overview`, `grabs`, `torrents`, `rss`, `configuration`).
- `web/templates/partials/*`: topbar, sidebar, composants partagés.
- `web/static/js/app.js`: logique UI centralisée.
- `web/static/css/app.css`: styles globaux.
- `config/settings.yml`, `config/settings-example.yml`: configuration runtime.
- `docs/`: architecture, plans et notes de release.

## Règles UI & Frontend (OBLIGATOIRE)
### Réutilisation avant création
Avant toute création de classe, composant, bouton, formulaire ou layout:
1. Rechercher un pattern existant (`ui-card`, `config-field`, `copy-field`, `btn`, `actions-bar`, `modal`).
2. Réutiliser ou étendre ce pattern.
3. Créer du nouveau uniquement si aucun pattern existant n’est adapté.

Conventions:
- CSS: noms explicites, préfixes par domaine (`config-*`, `rss-*`, `history-*`).
- Aucune duplication de styles/composants sans justification explicite en PR.
- Les actions critiques utilisent systématiquement le pattern inline confirmation via `data-confirming="true"` (jamais de `confirm()` navigateur).
- Toute action destructive/risquée (suppression, purge, désactivation, logout) doit passer par ce pattern (2 clics + reset auto).
- Les champs texte destinés à être copiés doivent utiliser le pattern `copy-field` (champ + bouton `Copier`) et non une implémentation locale ad hoc.
- Pour les champs éditables alignés visuellement avec les champs copiables, utiliser l’équivalent `edit-field` déjà en place.

## Réutilisation du code & APIs (SECTION CRITIQUE)
Toute feature commence par un inventaire de l’existant:
- helpers métier (`src/*`), fonctions DB (`src/db.py`), routes API (`src/api.py`), auth (`src/auth.py`).
Règles:
- Ne jamais recréer une fonction déjà disponible.
- Étendre une fonction/service existant avant d’en créer un nouveau.
- Centraliser la logique transversale dans modules partagés, pas dans la route/UI.
- Toute nouvelle route `/api/*` doit justifier l’absence d’équivalent.

## Commandes de développement
- `DATA_DIR=./data CONFIG_DIR=./config python src/main.py`: exécution locale.
- `docker-compose -f docker/docker-compose.dev.yml up --build`: environnement dev Docker.
- `python tools/history_limits_check.py`: contrôle limites history.

## Style de code & conventions
- Python: 4 espaces, `snake_case`, classes `PascalCase`.
- Logs: `logging.getLogger(__name__)`, messages courts, orientés diagnostic.
- Pas de linter imposé: conserver le style du fichier touché.

## Tests
- Ajouter des tests ciblés sur les flux modifiés (API, DB, scheduler, UI JS).
- Scripts temporaires: `test_*.py` uniquement en local.
- Vérifier systématiquement démarrage app + endpoints modifiés.

## Git, Commits & Pull Requests
- Commits: `feat:`, `fix:`, `refactor:`, `docs:`, `chore:`.
- PR obligatoire: quoi, pourquoi, impacts UI/API, risques, tests exécutés.
- Changement visuel: captures avant/après.

## Principes fondamentaux du projet
- Simplicité > complexité
- Réutilisation > duplication
- Cohérence UI > innovation isolée
- Code lisible > code “clever”
- Extensions progressives > refactor massif

## Sécurité & configuration
- Jamais de secrets en Git.
- Config via `settings.yml`/variables d’environnement.
- Les actions admin doivent rester protégées (session auth ou accès local contrôlé).
