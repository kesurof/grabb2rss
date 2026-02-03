# Plan de Restructuration 3A (Backend + Web + Prépa Tailwind/Alpine)

Ce document décrit un **processus pas à pas** pour réorganiser le dépôt selon l’option 3A :
- Backend Python dans `src/`
- UI (templates + assets) dans `web/`
- Préparation progressive pour Tailwind CSS + Alpine.js

Chaque étape est conçue pour être **suivie séquentiellement** et **reversible** si besoin.

---

## 0) Pré‑requis

- Avoir un commit propre avant de commencer.
- Vérifier que la branche courante est bien `dev` (ou une branche de refactor).
- Disposer d’un environnement local ou CI pour exécuter l’app après chaque étape.

---

## 1) Créer la nouvelle arborescence cible (Terminé)

Créer les dossiers suivants :

```
/src/                 # backend Python
/web/                 # UI (templates + static)
/web/assets/           # futur build Tailwind/Alpine
/config/              # config, schémas, conventions
/docker/              # Dockerfile, entrypoint, compose
```

Statut : terminé le 3 février 2026.

---

## 2) Déplacer le backend dans /src (Terminé)

Déplacer tous les modules Python de la racine vers `src/` :

Exemples :
- `api.py` → `src/api.py`
- `main.py` → `src/main.py`
- `auth.py`, `db.py`, `scheduler.py`, etc. → `src/`

Actions à prévoir :
- Mettre à jour les imports internes si nécessaire.
- Adapter les chemins relatifs qui pointent sur `templates/`, `static/` ou `VERSION`.

Statut : terminé le 3 février 2026.

---

## 3) Déplacer l’UI dans /web (Terminé)

Déplacer :
- `templates/` → `web/templates/`
- `static/` → `web/static/`

Puis mettre à jour :
- Les chemins de `TEMPLATE_DIR` et `STATIC_DIR` dans `src/api.py`.
- Les références `href`/`src` si besoin (normalement inchangées).

Statut : terminé le 3 février 2026.

---

## 4) Centraliser les chemins globaux (Terminé)

Créer un module de chemins (ex: `src/paths.py`) avec :
- `PROJECT_ROOT`
- `WEB_DIR`
- `TEMPLATES_DIR`
- `STATIC_DIR`
- `VERSION_FILE`

Et remplacer les chemins codés en dur par ces constantes.

Statut : terminé le 3 février 2026.

---

## 5) Adapter Docker et runtime (Terminé)

Déplacer :
- `Dockerfile` → `docker/Dockerfile`
- `entrypoint.sh` → `docker/entrypoint.sh`
- `docker-compose*.yml` → `docker/`

Puis adapter :
- `COPY` et `WORKDIR`
- Le lancement (`python /app/src/main.py`)
- Les chemins `/app/web` et `/app/VERSION`

Statut : terminé le 3 février 2026.

---

## 6) Préparer le futur frontend (Tailwind / Alpine) (Terminé)

Ajouter un scaffold minimal :

```
/web/assets/
  /css/   # futur entry Tailwind
  /js/    # futur entry Alpine
```

Option : ajouter un `package.json` minimal (sans build pour l’instant).

Statut : terminé le 3 février 2026.

---

## 7) Ajuster la config et la version (Terminé)

S’assurer que :
- `VERSION` reste à la racine du repo.
- Le backend lit toujours la version via `version.py` en utilisant `PROJECT_ROOT/VERSION`.

Statut : terminé le 3 février 2026.

---

## 8) Vérifications intermédiaires

Après chaque étape clé :

- Lancer l’app localement (`python src/main.py` ou via Docker)
- Vérifier `/health`, `/api/info`
- Vérifier `/login` et le chargement du JS

---

## 9) Nettoyage final

Supprimer les anciens dossiers vides à la racine.
Mettre à jour :
- `README.md` (paths)
- `docs/`
- `AGENTS.md` (structure)

---

## 10) Rollback possible

Si une étape casse l’app :
- Revenir au commit précédent.
- Refaire la migration avec corrections ciblées.

---

## Résultat attendu

Un dépôt clair, modulaire, prêt pour :
- migration progressive vers Tailwind
- intégration Alpine
- maintenance backend facilitée
