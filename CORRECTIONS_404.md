# Corrections des erreurs 404 - Routes

## Problèmes identifiés et corrigés

### 1. ✅ Ordre des middlewares clarifié

**Avant :**
```python
# Ordre confus avec commentaire imprécis
app.add_middleware(AuthMiddleware)
app.add_middleware(SetupRedirectMiddleware)
```

**Après :**
```python
# Ordre d'ajout : CORS → Auth → SetupRedirect
# Ordre d'exécution : SetupRedirect → Auth → CORS
#
# SetupRedirect s'exécute en premier : redirige vers /setup si premier lancement
# Auth s'exécute ensuite : vérifie l'authentification
# CORS s'exécute en dernier : ajoute les headers CORS

app.add_middleware(CORSMiddleware, ...)
app.add_middleware(AuthMiddleware)
app.add_middleware(SetupRedirectMiddleware)
```

### 2. ✅ Exclusions du SetupRedirectMiddleware corrigées

**Avant :**
```python
# Ne pas rediriger si sur /login ou /
if request.url.path in ['/login', '/']:
    return await call_next(request)
```

**Problème :** `/` était exclu de la redirection vers `/setup`, ce qui permettait d'accéder au dashboard même si le setup n'était pas complété.

**Après :**
```python
# Ne pas rediriger /login (nécessaire pour l'authentification)
if request.url.path == '/login':
    return await call_next(request)
```

**Résultat :** Maintenant, `/` redirige correctement vers `/setup` si le setup n'est pas complété, et vers `/login` si l'authentification est requise.

### 3. ✅ Chemins absolus pour les templates

**Avant :**
```python
TEMPLATE_DIR = Path(__file__).parent / "templates"
```

**Après :**
```python
TEMPLATE_DIR = Path(__file__).parent.absolute() / "templates"
```

**Résultat :** Évite les problèmes de résolution de chemin dans Docker ou avec des liens symboliques.

### 4. ✅ Ordre mount/middlewares/routes réorganisé

**Avant :**
```python
templates = Jinja2Templates(directory=str(TEMPLATE_DIR))
app.mount("/static", StaticFiles(...))

# ... middlewares ...

app.include_router(setup_router)
app.include_router(auth_router)
```

**Après :**
```python
templates = Jinja2Templates(directory=str(TEMPLATE_DIR))

# Inclure les routes AVANT les middlewares
app.include_router(setup_router)
app.include_router(auth_router)

# Monter les fichiers statiques
app.mount("/static", StaticFiles(...))
app.mount("/torrents", StaticFiles(...))

# Ajouter les middlewares
app.add_middleware(CORSMiddleware, ...)
app.add_middleware(AuthMiddleware)
app.add_middleware(SetupRedirectMiddleware)
```

**Résultat :** Ordre plus logique et évite les conflits potentiels.

### 5. ✅ Instance Jinja2Templates unifiée

**Avant :** Deux instances séparées dans `api.py` et `setup_routes.py` avec des chemins relatifs différents.

**Après :** Utilisation de chemins absolus identiques dans les deux fichiers.

```python
# Dans api.py et setup_routes.py
TEMPLATE_DIR = Path(__file__).parent.absolute() / "templates"
templates = Jinja2Templates(directory=str(TEMPLATE_DIR))
```

**Résultat :** Évite les incohérences de résolution de chemin.

## Comportement final des routes

### Scénario 1 : Setup non complété

- `/` → Redirige vers `/setup` (307)
- `/login` → Accessible (200)
- `/dashboard` → Redirige vers `/setup` (307)
- `/setup` → Affiche le formulaire de setup (200)
- `/health`, `/debug`, `/test`, `/minimal` → Accessibles (200)
- Routes API `/api/*` → Accessibles (200 ou authentification requise)

### Scénario 2 : Setup complété, Auth désactivée

- `/` → Affiche le dashboard (200)
- `/login` → Affiche la page de login (200)
- `/dashboard` → Affiche le dashboard (200)
- `/setup` → Redirige vers `/` (307)
- Toutes les autres routes → Accessibles (200)

### Scénario 3 : Setup complété, Auth activée, Non authentifié

- `/` → Redirige vers `/login` (307)
- `/login` → Affiche la page de login (200)
- `/dashboard` → Redirige vers `/login` (307)
- `/setup` → Redirige vers `/` puis vers `/login` (307)
- Routes API → Retourne 401 (sauf routes publiques)
- Routes RSS → Accessible localement ou avec API key

### Scénario 4 : Setup complété, Auth activée, Authentifié

- `/` → Affiche le dashboard (200)
- `/login` → Affiche la page de login (200)
- `/dashboard` → Affiche le dashboard (200)
- `/setup` → Redirige vers `/` (307)
- Toutes les routes → Accessibles (200)

## Fichiers modifiés

1. **api.py**
   - Réorganisation de l'ordre mount/middlewares/routes
   - Correction des exclusions dans SetupRedirectMiddleware
   - Clarification de l'ordre des middlewares
   - Utilisation de chemins absolus pour templates

2. **setup_routes.py**
   - Utilisation de chemins absolus pour templates
   - Cohérence avec api.py

3. **test_routes.py** (nouveau)
   - Script de test pour vérifier toutes les routes

## Tests à effectuer après déploiement

1. Supprimer `/config/settings.yml` (ou créer un nouveau container)
2. Accéder à `http://localhost:8000/` → Doit rediriger vers `/setup`
3. Compléter le setup
4. Accéder à `http://localhost:8000/` → Doit afficher le dashboard (ou rediriger vers `/login` si auth activée)
5. Tester `/login`, `/dashboard`, `/api/*` pour vérifier l'authentification
6. Tester `/health`, `/debug` pour vérifier les routes publiques

## Conclusion

Toutes les routes devraient maintenant fonctionner correctement. Le comportement est cohérent et prévisible dans tous les scénarios.
