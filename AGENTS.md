# Directives de Répertoire

## Structure du projet et organisation des modules
- **Entrée** : `main.py` (démarre FastAPI), configuration centralisée dans `config.py` et schéma dans `settings_schema.py`.  
- **API** : `api.py` + routes `auth_routes.py`, `setup_routes.py`.  
- **Logique métier** : `prowlarr.py`, `radarr_sonarr.py`, `torrent.py`, `rss.py`, `scheduler.py`, `db.py`.  
- **UI** : templates Jinja2 dans `templates/`, assets dans `static/`.  
- **Docs** : `docs/` (installation, plan de prod, etc.).  
- **Docker** : `Dockerfile`, `docker-compose*.yml`, `entrypoint.sh`.  
Exemple de configuration: `/config/settings.yml` ; données: `/app/data/`.

## Commandes de construction, de test et de développement
- **Dev Docker** :  
  `docker-compose -f docker-compose.dev.yml up --build`  
  Lance l’app en mode développement.  
- **Exécution locale** :  
  `pip install -r requirements.txt` puis `python main.py`  
  Démarre l’API sur `APP_HOST:APP_PORT` (voir `config.py`).  
- **Prod ASGI** :  
  `WEB_CONCURRENCY=2 gunicorn api:app --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000`  
  Ajustez `WEB_CONCURRENCY` selon CPU/RAM.

## Style de codage et conventions de nommage
- **Python** : 4 espaces, `snake_case`, `PascalCase` pour classes.  
- **Logs** : utilisez `logging.getLogger(__name__)` (messages concis, français).  
- **Formatage/Lint** : pas d’outil imposé (pas de Black/Ruff configurés). Restez cohérent avec l’existant.

## Directives de test
- **Script principal** : `python test_history_limits.py`  
  Valide l’historique Prowlarr/Radarr/Sonarr.  
- **Convention** : tests/scripts nommés `test_*.py` à la racine.  
- **Couverture** : pas d’exigence formelle ; ajouter des tests ciblés lors d’ajouts logiques.

## Directives de Commit et de Pull Request
- **Commits** : usage courant de préfixes type Conventional Commits (`feat:`, `fix:`, `docs:`), avec merges GitHub.  
- **PR** : décrire le changement, l’impact, lier les issues si besoin.  
  - UI modifiée → capture d’écran.  
  - Mentionner les tests exécutés (ou “non exécutés”).

## Sécurité & configuration
- **Secrets** : ne jamais commiter de clés API. Utiliser `settings.yml` ou variables d’env.  
- **Ports** : par défaut `8000`.  
- **CORS / cookies** : configurez via `settings.yml` pour la prod.

## Versionnement et releases
- **Source de vérité** : la version applicative vit uniquement dans `VERSION`.  
- **SemVer** : suivez `MAJOR.MINOR.PATCH` (compatibilité API, nouvelles features, correctifs).  
- **Gouvernance** : modifiez `VERSION` via une PR dédiée (ou une étape de release) juste avant de taguer `vX.Y.Z`.  
- **CI/CD** : les workflows refusent une release si le tag Git ne correspond pas à `VERSION`.
