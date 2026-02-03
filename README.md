# 📡 grabb2rss

[![Docker](https://img.shields.io/badge/docker-ghcr.io-blue)](https://ghcr.io/kesurof/grabb2rss)
[![Python](https://img.shields.io/badge/python-3.11+-green)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-lightgrey)](LICENSE)

**Convertisseur Prowlarr vers RSS** avec support multi-tracker, filtrage intelligent et interface web moderne.

Transformez vos grabs Prowlarr en flux RSS pour le seeding automatique avec vos clients torrent préférés.

---

## ✨ Fonctionnalités

- 🔄 **Synchronisation Automatique** - Récupère les torrents depuis Prowlarr selon un intervalle défini
- 📡 **Flux RSS** - Génère des flux RSS/JSON compatibles avec ruTorrent, qBittorrent, Transmission
- 🎯 **Filtrage Intelligent** - Intégration optionnelle Radarr/Sonarr pour afficher uniquement les grabs souhaités
- 🏷️ **Multi-Tracker** - Filtrage des flux par tracker
- 🔍 **Déduplication** - Détection intelligente des doublons
- 🗑️ **Purge Automatique** - Nettoyage automatique des anciens torrents
- 💻 **Interface Web Moderne** - Dashboard avec statistiques, logs et configuration
- 🐳 **Prêt pour Docker** - Gestion des permissions PUID/PGID à la LinuxServer.io
- 🚀 **Setup Wizard** - Configuration en français au premier lancement

---

## 🚀 Installation Rapide

### Prérequis

- Docker et Docker Compose installés
- Une instance Prowlarr en fonctionnement
- (Optionnel) Radarr et/ou Sonarr pour le filtrage

### Méthode Recommandée (Image Pré-construite)

**Installation en 3 étapes :**

1. **Télécharger le fichier docker-compose.yml**

```bash
mkdir grabb2rss && cd grabb2rss
curl -o docker-compose.yml https://raw.githubusercontent.com/kesurof/grabb2rss/main/docker/docker-compose.example.yml
```

Ou créez manuellement le fichier `docker-compose.yml` :

```yaml
version: "3.8"

services:
  grabb2rss:
    image: ghcr.io/kesurof/grabb2rss:latest
    container_name: grabb2rss
    environment:
      - PUID=1000  # Votre User ID (trouvez-le avec: id -u)
      - PGID=1000  # Votre Group ID (trouvez-le avec: id -g)
      - TZ=Europe/Paris  # Votre timezone
    volumes:
      - ./config:/config
      - ./data:/app/data
    ports:
      - "8000:8000"
    restart: unless-stopped
```

2. **Démarrer le container**

```bash
docker-compose up -d
```

3. **Configurer via le Setup Wizard**

Ouvrez votre navigateur sur **http://localhost:8000**

Vous serez automatiquement redirigé vers le **Setup Wizard** où vous pourrez configurer :
- ✅ Prowlarr (URL + Clé API) - **Obligatoire**
- ✅ Radarr (URL + Clé API) - **Obligatoire**
- ✅ Sonarr (URL + Clé API) - **Obligatoire**
- ✅ Paramètres de synchronisation et rétention

**C'est tout !** 🎉 Votre configuration est sauvegardée dans `/config/settings.yml`

---

## 📖 Utilisation

### Flux RSS

Une fois configuré, accédez à vos flux RSS :

**Flux global (tous les trackers) :**
```
http://localhost:8000/rss
```

**Filtré par tracker :**
```
http://localhost:8000/rss/tracker/NomDuTracker
```

**Format JSON :**
```
http://localhost:8000/rss.json
```

**Authentification (API Keys) :**

Ajoutez un header HTTP dans votre client torrent :

- `X-API-Key: VOTRE_CLE`
- ou `Authorization: Bearer VOTRE_CLE`

### Configuration

La configuration peut être modifiée :
- ✅ Via l'interface web : http://localhost:8000 (onglet Configuration)
- ✅ En éditant directement `/config/settings.yml`

### Valeurs par défaut

Résumé des valeurs par défaut principales :

- `sync.interval`: `3600` (1h)
- `sync.retention_hours`: `168` (7 jours)
- `sync.dedup_hours`: `168` (7 jours)
- `sync.auto_purge`: `true`
- `prowlarr.history_page_size`: `500`
- `rss.scheme`: `http`
- `rss.domain`: `localhost:8000`
- `cors.allow_origins`: `http://localhost:8000`, `http://127.0.0.1:8000`
- `torrents.expose_static`: `false`
- `torrents_download.max_size_mb`: `50`
- `network.retries`: `3`
- `network.backoff_seconds`: `1.0`
- `network.timeout_seconds`: `10`
- `logging.level`: `INFO`

### Cookies de session (HTTPS)

En production derrière HTTPS, activez les cookies sécurisés pour l'authentification :

- Dans `/config/settings.yml` (section `auth`) :

```yaml
auth:
  cookie_secure: true
```

- Ou via la variable d'environnement `AUTH_COOKIE_SECURE=true`

### Sessions persistantes

Les sessions sont stockées en base de données SQLite afin de survivre aux redémarrages
et permettre un scale-out léger (multi-workers).

### CORS (origines autorisées)

Par défaut, seules les origines locales sont autorisées. Pour la prod, définissez la liste :

- Dans `/config/settings.yml` :

```yaml
cors:
  allow_origins:
    - "https://grabb2rss.example.com"
    - "https://dashboard.example.com"
```

- Ou via `CORS_ALLOW_ORIGINS` (séparé par virgules) :

```
CORS_ALLOW_ORIGINS=https://grabb2rss.example.com,https://dashboard.example.com
```

### Accès aux fichiers torrents

Par défaut, le dossier `/torrents` n'est **pas** exposé. Pour l'activer explicitement :

- Dans `/config/settings.yml` :

```yaml
torrents:
  expose_static: true
```

- Ou via `TORRENTS_EXPOSE_STATIC=true`

### Téléchargement des torrents (streaming + limite)

Le téléchargement est effectué en streaming avec une limite de taille.
Définissez la taille max (MB) :

- Dans `/config/settings.yml` :

```yaml
torrents_download:
  max_size_mb: 50
```

- Ou via `TORRENTS_MAX_SIZE_MB=50`

### Niveau de logs

Définissez le niveau de logs (ex: `DEBUG`, `INFO`, `WARNING`, `ERROR`) :

- Dans `/config/settings.yml` :

```yaml
logging:
  level: "INFO"
```

- Ou via `LOG_LEVEL=INFO`

### API

Consultez la documentation API complète sur http://localhost:8000/docs

Endpoints principaux :
- `GET /api/stats` - Statistiques
- `GET /api/grabs` - Liste des grabs
- `GET /api/trackers` - Trackers disponibles
- `POST /api/sync/trigger` - Synchronisation manuelle
- `GET /health` - Health check

---

## 📊 Architecture

```
┌─────────────┐
│  Prowlarr   │ ← Récupère les torrents depuis les indexeurs
└──────┬──────┘
       │ API
       ▼
┌─────────────┐
│  grabb2rss   │ ← Récupère les grabs, génère les flux RSS
└──────┬──────┘
       │ Flux RSS
       ▼
┌─────────────┐
│   Client    │ ← Télécharge automatiquement depuis le flux RSS
│  Torrent    │   (ruTorrent, qBittorrent, etc.)
└─────────────┘
```

### Filtrage inclus

```
┌──────────┐  ┌──────────┐
│  Radarr  │  │  Sonarr  │ ← Clients de téléchargement
└────┬─────┘  └────┬─────┘
     │             │
     └─────┬───────┘
           │ API (filtre les torrents grabbed)
           ▼
     ┌─────────────┐
     │  grabb2rss   │ ← Affiche uniquement les torrents grabbed
     └─────────────┘
```

---

## 🛠️ Dépannage

### Le container ne démarre pas

Vérifiez les logs :
```bash
docker logs grabb2rss
```

### Problèmes de permissions

Vérifiez que PUID/PGID correspondent à votre utilisateur :
```bash
id $USER
```

Mettez à jour docker-compose.yml et recréez le container :
```bash
docker-compose down
docker-compose up -d
```

### Aucun torrent n'apparaît

1. Vérifiez que la clé API Prowlarr est correcte
2. Vérifiez que Prowlarr a des grabs récents (page Historique)
3. Déclenchez une synchronisation manuelle dans l'interface web
4. Consultez les logs dans l'onglet Admin

### Reconfigurer l'application

Si vous souhaitez revenir au Setup Wizard :

```bash
docker-compose down
rm config/settings.yml
docker-compose up -d
```

---

## 🔄 Mise à Jour

Pour mettre à jour vers la dernière version :

```bash
docker-compose pull
docker-compose up -d
```

Votre configuration dans `/config` sera préservée.

---

## 📚 Documentation

- [Processus de Release](docs/release-process.md)

### Versionnement

La version applicative est **exclusivement** définie par le fichier `VERSION` à la racine.
Toutes les expositions (API, UI, Docker, headers, logs) en dépendent automatiquement.

### Production (ASGI)

Pour un déploiement prod, utilisez un runner ASGI type Gunicorn + Uvicorn :

```bash
WEB_CONCURRENCY=2 gunicorn src.api:app \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000 \
  --timeout 60
```

Variables utiles :

- `WEB_CONCURRENCY`: nombre de workers (ex: `2`)
- `LOG_LEVEL`: niveau de logs (`INFO`, `WARNING`, etc.)

Recommandation (adapter aux capacités) :

- `WEB_CONCURRENCY = min(4, max(2, CPU * 2))`
- Ajustez si la RAM est limitée (ex: 512MB → 1 worker).

Exemple docker-compose :

```yaml
services:
  grabb2rss:
    image: ghcr.io/kesurof/grabb2rss:latest
    ports:
      - "8000:8000"
    environment:
      - LOG_LEVEL=INFO
    command: >
      sh -c 'WORKERS=${WEB_CONCURRENCY:-$((2 * $(nproc)))}; \
      if [ "$WORKERS" -lt 2 ]; then WORKERS=2; fi; \
      if [ "$WORKERS" -gt 4 ]; then WORKERS=4; fi; \
      gunicorn src.api:app --worker-class uvicorn.workers.UvicornWorker --workers "$WORKERS" --bind 0.0.0.0:8000 --timeout 60'
```

- [Installation Détaillée](docs/INSTALLATION.md)
- [Guide Rapide](docs/QUICKSTART.md)
- [Configuration qBittorrent](docs/QBITTORRENT_SETUP.md)
- [Configuration Réseau](docs/NETWORK_SETUP.md)

---

## 🤝 Contribuer

Les contributions sont les bienvenues ! Pour contribuer :

1. Forkez le dépôt
2. Créez une branche pour votre fonctionnalité
3. Faites vos modifications
4. Soumettez une pull request

### Build Local (Développeurs)

Si vous souhaitez builder localement pour le développement :

```bash
git clone https://github.com/kesurof/grabb2rss.git
cd grabb2rss
docker-compose -f docker/docker-compose.dev.yml up --build
```

---


## 🙏 Remerciements

- Inspiré par les standards de gestion des permissions de [LinuxServer.io](https://www.linuxserver.io/)
- Construit avec [FastAPI](https://fastapi.tiangolo.com/)
- Utilise [APScheduler](https://apscheduler.readthedocs.io/) pour la planification des tâches

---

## 📞 Support

- 🐛 [Signaler un Bug](https://github.com/kesurof/grabb2rss/issues)
- 💬 [Discussions](https://github.com/kesurof/grabb2rss/discussions)
- 📖 [Documentation](https://github.com/kesurof/grabb2rss/wiki)

---

**Fait avec ❤️ pour la communauté self-hosting**
