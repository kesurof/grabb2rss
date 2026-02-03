# Plan de corrections pour une mise en production fiable

> Objectif : établir un fil conducteur clair, priorisé et actionnable pour amener le projet au niveau “production”.
> Les actions ci-dessous sont regroupées par priorité et par domaine (sécurité, robustesse, observabilité, etc.).

## 1) Priorité critique — Sécurité & accès

### 1.1 Sécuriser les cookies de session (Terminé)
- **Action** : passer `secure=True` en production et rendre le paramètre configurable (ex: `AUTH_COOKIE_SECURE`).
- **Raison** : éviter l’interception des sessions sur des connexions non chiffrées.
- **Livrable** : settings.yml + variables d’environnement + doc d’usage.
- **Statut** : terminé le 3 février 2026.

### 1.2 Sortir les API keys des query params (Terminé)
- **Action** : accepter les clés via header (`Authorization: Bearer <key>` ou `X-API-Key`) et supprimer l’usage de la query string.
- **Raison** : les query params fuitent dans les logs/proxy.
- **Livrable** : middleware auth + documentation mise à jour.
- **Statut** : terminé le 3 février 2026.

### 1.3 Restreindre le CORS en production (Terminé)
- **Action** : remplacer `allow_origins=["*"]` par une liste d’origines autorisées configurable.
- **Raison** : limiter l’exposition cross‑origin.
- **Livrable** : config + doc.
- **Statut** : terminé le 3 février 2026.

### 1.4 Protéger l’accès aux fichiers torrents (Terminé)
- **Action** : ne monter `/torrents` qu’en mode protégé (auth ou désactivé par défaut).
- **Raison** : éviter l’exposition de contenus sensibles.
- **Livrable** : feature flag (ex: `TORRENTS_EXPOSE_STATIC`) + doc.
- **Statut** : terminé le 3 février 2026.

---

## 2) Priorité haute — Robustesse & résilience

### 2.1 Requêtes réseau avec retries/backoff (Terminé)
- **Action** : ajouter un mécanisme de retry (ex: 3 tentatives, backoff exponentiel) sur les appels Prowlarr/Radarr/Sonarr.
- **Raison** : éviter les échecs ponctuels qui cassent un cycle de sync.
- **Livrable** : wrapper réseau réutilisable + logs.
- **Statut** : terminé le 3 février 2026.

### 2.2 Téléchargement torrent en streaming (Terminé)
- **Action** : utiliser `stream=True`, écrire en chunks, limiter la taille max.
- **Raison** : éviter l’explosion mémoire et les fichiers invalides.
- **Livrable** : gestion d’erreur claire + paramètre `TORRENTS_MAX_SIZE_MB`.
- **Statut** : terminé le 3 février 2026.

### 2.3 Gestion d’erreurs cohérente (Terminé)
- **Action** : normaliser les messages d’erreur et éviter les `print()` silencieux.
- **Raison** : diagnostiquer rapidement en prod.
- **Livrable** : logger commun + messages concis en français.
- **Statut** : terminé le 3 février 2026.

---

## 3) Priorité haute — Observabilité & logs

### 3.1 Remplacer les `print()` par un logger (Terminé)
- **Action** : utiliser `logging.getLogger(__name__)` partout, niveaux cohérents.
- **Raison** : centraliser logs, filtrer, router.
- **Livrable** : config logging unique.
- **Statut** : terminé le 3 février 2026.

### 3.2 Ajouter des métriques applicatives
- **Action** : exposer métriques (ex: `/metrics` Prometheus) pour les cycles sync.
- **Raison** : visibilité opérationnelle (durée sync, erreurs, volumétrie).
- **Livrable** : endpoint metrics + doc.

---

## 4) Priorité moyenne — Configuration & validation

### 4.1 Validation stricte du settings.yml (Terminé)
- **Action** : utiliser un schéma (Pydantic/Schema) et retourner les erreurs lisibles.
- **Raison** : éviter un démarrage en état partiellement cassé.
- **Livrable** : validateurs + tests unitaires ciblés.
- **Statut** : terminé le 3 février 2026.

### 4.2 Clarifier les valeurs par défaut (Terminé)
- **Action** : documenter clairement les paramètres critique (intervalle sync, rétention, etc.).
- **Raison** : faciliter la mise en production sans surprises.
- **Livrable** : doc `docs/` + README.
- **Statut** : terminé le 3 février 2026.

---

## 5) Priorité moyenne — Déploiement & scaling

### 5.1 Runner ASGI pour production (Terminé)
- **Action** : documenter (ou fournir) un lancement via Gunicorn + Uvicorn workers.
- **Raison** : meilleure résilience et gestion de charge.
- **Livrable** : doc de déploiement + variables `WEB_CONCURRENCY`.
- **Statut** : terminé le 3 février 2026.

### 5.2 Sessions persistantes (Terminé)
- **Action** : stocker les sessions en DB ou Redis.
- **Raison** : éviter la perte de sessions au redémarrage et permettre le scale‑out.
- **Livrable** : couche de stockage + migration légère.
- **Statut** : terminé le 3 février 2026.

---

## 6) Tests & validation

### 6.1 Tests ciblés sur la config
- **Action** : tests `test_*.py` pour valider les schémas et les erreurs de config.
- **Raison** : fiabiliser les changements structurants.
- **Livrable** : tests unitaires simples, exécutables localement.

### 6.2 Tests intégration (optionnel)
- **Action** : un script simple qui simule un cycle de sync avec mocks.
- **Raison** : détecter les régressions réseau.
- **Livrable** : script de test d’intégration.

---

## 7) Checklist de livraison
- [x] Cookies sécurisés activés en prod
- [x] CORS restreint
- [x] API keys via header
- [x] `/torrents` protégé ou désactivé
- [x] Logs centralisés sans `print()`
- [ ] Retries/backoff activés
- [ ] Streaming + limite taille torrents
- [ ] Validation stricte de la config
- [ ] Documentation de déploiement mise à jour
