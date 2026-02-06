# Plan d'action backend (étape par étape)

Objectif: sécuriser le backend, réduire les risques majeurs, et stabiliser l’exploitation sans casser l’existant.

**Étape 1.1: Cadrer le périmètre**
- [x] Lister les endpoints sensibles en production (auth, setup, purge, logs, config). Relevé: `/api/auth/login`, `/api/auth/keys`, `/api/auth/keys/generate`, `/api/auth/keys/{key}`, `/api/setup/test-prowlarr`, `/api/setup/save`, `/api/config` (GET/POST), `/api/purge/all`, `/api/purge/retention`, `/api/torrents/{filename}`, `/api/torrents/purge-all`, `/api/torrents/cleanup-orphans`, `/api/logs/system`, `/api/logs/purge-all`, `/api/logs/{log_id}`, `/api/db/vacuum`, `/api/cache/clear`, `/api/sync/trigger`, `/api/test-history-limits`.
- [x] Définir le niveau d’exposition public attendu (RSS public oui/non, UI protégée oui/non). Position: UI protégée quand l’auth est activée; RSS non public si auth activée, mais accessible via API key; si auth désactivée, RSS et UI deviennent publics; `/torrents` n’est exposé que si `TORRENTS_EXPOSE_STATIC=true`.
- [x] Identifier les données sensibles manipulées (credentials, tokens, URLs privées, journaux). Données: clés API (Prowlarr + API keys internes), sessions (cookie `session_token`), URLs de trackers, fichiers `.torrent`, logs de synchro/système, configuration applicative.
- [x] Définir les profils d’accès attendus (admin, utilisateur, accès public). Profils: public uniquement si auth désactivée; utilisateur authentifié via session pour l’UI et les API; accès RSS via API key; actions admin pour maintenance/purge/config.
- [x] Recenser les intégrations externes (Prowlarr, Radarr, Sonarr) et leurs points d’entrée. Intégrations: Prowlarr (API URL + key), Radarr/Sonarr (API URLs), consommateurs RSS (rutorrent/qBittorrent/Transmission), potentiellement reverse proxy.
- [x] Clarifier les environnements concernés (dev, test, prod) et leurs niveaux d’exposition. Environnements: dev via `docker-compose.dev.yml`; prod via `gunicorn` sur port `8000`; test = environnement intermédiaire identique à prod mais non public.
- [x] Fixer les critères d’acceptation sécurité pour cette itération (ex: pas de suppression hors `TORRENT_DIR`, accès admin verrouillé). Critères: validation stricte des fichiers `.torrent`, blocage des routes admin si auth désactivée et setup complété, rate limit login, RSS basé sur domaine configuré, permissions `TORRENT_DIR` durcies.

**Étape 1.2: Audit rapide et référencement des risques**
- [x] Cartographier les flux et points d’entrée externes (API, UI, RSS). Flux: Prowlarr -> API (grabs) -> DB -> génération RSS/JSON -> clients RSS; UI -> API (config, logs, torrents, purge); Radarr/Sonarr -> lecture RSS; accès direct `/torrents` si exposé.
- [x] Identifier les risques majeurs (traversal, auth faible, bruteforce, host header). Risques: suppression arbitraire via `filename` (traversal), routes admin ouvertes si auth désactivée, brute-force login, host header utilisé pour générer des URLs RSS, exposition `/torrents` en statique, purge non protégée.
- [x] Classer par impact et effort (P0, P1, P2). P0: traversal/suppression, admin routes ouvertes; P1: brute-force login, host header RSS; P2: permissions `TORRENT_DIR`, exposition `/torrents`, durcissement logs/retention.

**Étape 2: Corriger le risque de suppression de fichiers (traversal)**
- [x] Valider strictement `filename` côté API.
- [x] Refuser tout séparateur de chemin et forcer l’extension `.torrent`.
- [x] Vérifier que le chemin résolu reste dans `TORRENT_DIR`.

**Étape 3: Renforcer le stockage des mots de passe**
- [x] Remplacer SHA-256 + salt par `bcrypt` via `passlib` (hash par défaut).
- [x] Prévoir un rehash au login si l’ancien format est détecté (migration transparente).
- [ ] Documenter la migration dans `docs/`.

**Étape 4: Verrouiller les routes admin quand l’auth est désactivée**
- [x] Bloquer `POST /api/config`, `/api/setup/save`, `/api/torrents/purge-all`, `/api/logs/purge-all` si `setup_completed` est vrai et auth désactivée.
- [ ] Autoriser en lecture seule si besoin (GET /api/config par exemple).

**Étape 5: Mettre une protection anti-bruteforce**
- [x] Ajouter un rate limit simple sur `/api/auth/login` (IP + fenêtre glissante).
- [x] Loguer les tentatives échouées.

**Étape 6: Durcir la génération des URLs RSS**
- [x] Utiliser `RSS_DOMAIN` par défaut et refuser les `Host` non autorisés.
- [x] Ajouter une liste blanche optionnelle.

**Étape 7: Réduire les permissions sur `TORRENT_DIR`**
- [x] Passer à `0o755` par défaut (ou `0o775` si besoin).
- [ ] Documenter le paramétrage Docker/UID/GID.

