# Templates

Ce dossier est destiné à contenir les templates HTML de l'application.

## Structure proposée

```
templates/
├── pages/
│   ├── login.html          # Page de connexion
│   ├── dashboard.html      # Page principale de l'interface web
│   └── setup.html          # Page de configuration initiale
├── partials/
│   ├── header.html         # En-tête commun
│   ├── footer.html         # Pied de page commun
│   └── navigation.html     # Navigation/tabs
└── README.md
```

## Statut actuel

Actuellement, les pages HTML sont générées inline dans les fichiers Python :
- `api.py` : Contient le HTML de la page principale (dashboard, login)
- `setup_routes.py` : Contient le HTML de la page de setup

## Migration future vers Jinja2

Pour améliorer la maintenabilité du code, une future migration vers des templates Jinja2 séparés est recommandée :

1. Installer/configurer Jinja2Templates pour FastAPI
2. Extraire le HTML des fichiers Python vers des templates séparés
3. Utiliser `TemplateResponse` au lieu de `HTMLResponse`
4. Centraliser les styles CSS et JavaScript dans des fichiers séparés

## Avantages de la séparation

- **Meilleure maintenabilité** : Séparation claire entre logique et présentation
- **Réutilisabilité** : Partials pour éviter la duplication
- **Lisibilité** : Code Python plus clair sans HTML inline
- **Collaboration** : Facilite le travail en équipe (frontend/backend)
