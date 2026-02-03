# Directives de Répertoire

## Structure du projet et organisation des modules
- **Entrée principale** : `main.py` démarre l’API FastAPI via Uvicorn.  
- **API et routes** : `api.py`, `auth_routes.py`, `setup_routes.py`.  
- **Données et logique** : `db.py`, `models.py`, `rss.py`, `scheduler.py`, `torrent.py`, `prowlarr.py`, `radarr_sonarr.py`.  
- **Configuration** : `config.py` et fichiers Docker (`docker-compose*.yml`).  
- **UI** : templates Jinja2 dans `templates/` et assets dans `static/`.  
- **Docs** : guides dans `docs/`.  

## Commandes de construction, de test et de développement
- **Dev via Docker (recommandé)** :  
  `docker-compose -f docker-compose.dev.yml up --build`  
  Lance un environnement complet pour développement local.  
- **Exécution locale Python** :  
  `python main.py`  
  Démarre l’API sur l’hôte/port définis dans `config.py`.  
- **Dépendances** :  
  `pip install -r requirements.txt`  
  Installe les bibliothèques Python.  

## Style de codage et conventions de nommage
- **Python** : indentation 4 espaces, `snake_case` pour fonctions/variables, `PascalCase` pour classes.  
- **Logs et messages** : privilégier les messages concis et en français (cohérent avec l’UI).  
- **Formatage/Lint** : aucun outil imposé (ex. Black/Ruff non configurés). Soyez cohérent avec le style existant.  

## Directives de test
- **Script de vérification** : `python test_history_limits.py`  
  Teste les limites d’historique Prowlarr/Radarr/Sonarr selon la config locale.  
- **Convention** : les scripts de test sont au niveau racine et nommés `test_*.py`.  
- **Couverture** : pas d’exigence explicite ; privilégier des tests ciblés lors d’ajouts logiques.  

## Directives de Commit et de Pull Request
- **Messages de commit** : tendance aux préfixes type Conventional Commits (`feat:`, `fix:`, `refactor:`, `security:`) et parfois des merges automatiques.  
- **PR** : décrire le changement, l’impact utilisateur, et lier les issues si pertinentes.  
  - Si vous modifiez l’UI, fournissez une capture d’écran.  
  - Indiquez les commandes de test exécutées (ou pourquoi elles n’ont pas pu l’être).  

## Notes de configuration et sécurité
- **Secrets** : ne commitez jamais de clés API ; utilisez `settings.yml` ou variables d’environnement.  
- **Ports** : par défaut, l’app écoute sur `8000`.  
