# Architecture de Grabb2RSS

## Structure des dossiers

```
grabb2rss/
├── templates/              # Templates Jinja2
│   ├── base.html          # Template de base (layout commun)
│   └── pages/             # Pages de l'application
│       ├── dashboard.html # Interface principale
│       ├── login.html     # Page de connexion
│       └── setup.html     # Assistant de configuration
├── static/                # Fichiers statiques
│   ├── css/
│   │   └── style.css     # Tous les styles CSS (11 KB)
│   └── js/
│       └── app.js        # Tout le JavaScript (44 KB)
├── api.py                 # API FastAPI principale (743 lignes)
├── setup_routes.py        # Routes du setup wizard
├── auth_routes.py         # Routes d'authentification
└── ...
```

## Points importants pour le débogage

### 1. Fichiers statiques

Les fichiers CSS et JS sont servis depuis `/static/`:
- CSS: `http://localhost:8000/static/css/style.css`
- JS: `http://localhost:8000/static/js/app.js`

**IMPORTANT**: Les middlewares doivent autoriser `/static` dans les routes publiques !

### 2. Middlewares (ordre d'exécution)

L'ordre des middlewares dans api.py est CRITIQUE:

```python
app.add_middleware(SetupRedirectMiddleware)  # 1er - Redirige vers /setup si premier lancement
app.add_middleware(AuthMiddleware)           # 2ème - Gère l'authentification
```

Les deux middlewares doivent autoriser:
- `/static` - Fichiers CSS/JS
- `/api` - Routes API
- `/setup` - Assistant de configuration
- `/login` - Page de connexion
- `/health`, `/debug`, `/test` - Routes utilitaires

### 3. Templates Jinja2

Les templates utilisent le système de blocks:
- `{% block title %}` - Titre de la page
- `{% block content %}` - Contenu principal
- `{% block scripts %}` - Scripts JavaScript

**Validation**: Les templates peuvent être validés avec:
```bash
python3 -c "from jinja2 import Environment, FileSystemLoader; env = Environment(loader=FileSystemLoader('templates')); env.get_template('pages/dashboard.html')"
```

### 4. JavaScript

Le fichier `app.js` contient toute la logique JavaScript:
- Initialisation automatique au `DOMContentLoaded`
- Détection de la page (login vs dashboard)
- Gestion des onglets, charts, API calls, etc.

**Validation**: Le JavaScript peut être validé avec:
```bash
node --check static/js/app.js
```

### 5. CSS

Le fichier `style.css` contient tous les styles:
- Styles communs (body, buttons, forms)
- Styles spécifiques login
- Styles spécifiques dashboard
- Animations et media queries

## Débogage d'une page blanche

Si l'interface affiche une page blanche:

1. **Vérifier les fichiers statiques**:
   ```bash
   curl -I http://localhost:8000/static/css/style.css
   curl -I http://localhost:8000/static/js/app.js
   ```
   Devrait retourner `200 OK`

2. **Vérifier la console du navigateur** (F12):
   - Erreurs JavaScript ?
   - Fichiers 404 ?
   - Erreurs réseau ?

3. **Vérifier les middlewares**:
   - `/static` est-il dans les routes publiques ?
   - Les deux middlewares autorisent-ils `/static` ?

4. **Vérifier les templates**:
   - Les blocks Jinja2 sont-ils corrects ?
   - Le fichier base.html charge-t-il le CSS ?

5. **Vérifier les logs du serveur**:
   - Erreurs 500 ?
   - Exceptions Python ?

## Checklist de déploiement

- [ ] Les fichiers dans `static/` existent
- [ ] Les templates dans `templates/pages/` existent
- [ ] `/static` est dans les routes publiques des middlewares
- [ ] Le serveur démarre sans erreur
- [ ] Les fichiers statiques sont accessibles (200 OK)
- [ ] La console du navigateur ne montre pas d'erreur
- [ ] settings.yml est configuré (sinon redirection vers /setup)

## URLs de test

- http://localhost:8000/ - Dashboard (redirige vers /setup si non configuré)
- http://localhost:8000/setup - Assistant de configuration
- http://localhost:8000/login - Page de connexion (si auth activée)
- http://localhost:8000/health - Health check
- http://localhost:8000/minimal - Interface de test minimaliste
- http://localhost:8000/static/css/style.css - Test fichier CSS
- http://localhost:8000/static/js/app.js - Test fichier JS
