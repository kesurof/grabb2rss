# 📡 Grab2RSS

[![Version](https://img.shields.io/badge/version-2.6.1-blue)](https://github.com/kesurof/grabb2rss)
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
mkdir grab2rss && cd grab2rss
curl -o docker-compose.yml https://raw.githubusercontent.com/kesurof/grabb2rss/main/docker-compose.example.yml
```

Ou créez manuellement le fichier `docker-compose.yml` :

```yaml
version: "3.8"

services:
  grab2rss:
    image: ghcr.io/kesurof/grabb2rss:latest
    container_name: grab2rss
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
- ✅ Radarr (URL + Clé API) - Optionnel
- ✅ Sonarr (URL + Clé API) - Optionnel
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

### Configuration

La configuration peut être modifiée :
- ✅ Via l'interface web : http://localhost:8000 (onglet Configuration)
- ✅ En éditant directement `/config/settings.yml`

### API

Consultez la documentation API complète sur http://localhost:8000/docs

Endpoints principaux :
- `GET /api/stats` - Statistiques
- `GET /api/grabs` - Liste des grabs
- `GET /api/trackers` - Trackers disponibles
- `POST /api/sync/trigger` - Synchronisation manuelle
- `GET /health` - Health check

---

## ⚙️ Configuration Avancée

### User/Group IDs (PUID/PGID)

Suivant les standards LinuxServer.io, vous pouvez définir PUID et PGID pour matcher votre utilisateur hôte :

```bash
id $USER
# uid=1000(user) gid=1000(user) groups=1000(user)
```

Puis dans docker-compose.yml :
```yaml
environment:
  - PUID=1000
  - PGID=1000
```

Cela garantit que les fichiers créés par le container ont les bonnes permissions sur votre hôte.

### Paramètres Clés

| Variable | Défaut | Description |
|----------|--------|-------------|
| `PUID` | 1000 | User ID pour les permissions fichiers |
| `PGID` | 1000 | Group ID pour les permissions fichiers |
| `TZ` | Europe/Paris | Timezone du container |

Tous les autres paramètres sont configurables via le Setup Wizard ou l'interface web.

---

## 🐳 Docker Compose avec Traefik

```yaml
version: "3.8"

services:
  grab2rss:
    image: ghcr.io/kesurof/grabb2rss:latest
    container_name: grab2rss
    environment:
      - PUID=1000
      - PGID=1000
      - TZ=Europe/Paris
    volumes:
      - ./config:/config
      - ./data:/app/data
    networks:
      - traefik_proxy
    restart: unless-stopped
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.grab2rss.rule=Host(`rss.example.com`)"
      - "traefik.http.routers.grab2rss.entrypoints=https"
      - "traefik.http.routers.grab2rss.tls.certresolver=letsencrypt"

networks:
  traefik_proxy:
    external: true
```

---

## 📊 Architecture

```
┌─────────────┐
│  Prowlarr   │ ← Récupère les torrents depuis les indexeurs
└──────┬──────┘
       │ API
       ▼
┌─────────────┐
│  Grab2RSS   │ ← Récupère les grabs, génère les flux RSS
└──────┬──────┘
       │ Flux RSS
       ▼
┌─────────────┐
│   Client    │ ← Télécharge automatiquement depuis le flux RSS
│  Torrent    │   (ruTorrent, qBittorrent, etc.)
└─────────────┘
```

### Filtrage Optionnel

```
┌──────────┐  ┌──────────┐
│  Radarr  │  │  Sonarr  │ ← Clients de téléchargement
└────┬─────┘  └────┬─────┘
     │             │
     └─────┬───────┘
           │ API (filtre les torrents grabbed)
           ▼
     ┌─────────────┐
     │  Grab2RSS   │ ← Affiche uniquement les torrents grabbed
     └─────────────┘
```

---

## 🛠️ Dépannage

### Le container ne démarre pas

Vérifiez les logs :
```bash
docker logs grab2rss
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

- [Installation Détaillée](docs/INSTALLATION.md)
- [Guide Rapide](docs/QUICKSTART.md)
- [Configuration qBittorrent](docs/QBITTORRENT_SETUP.md)
- [Configuration Réseau](docs/NETWORK_SETUP.md)

---

## 🔐 Sécurité

**⚠️ Important :** Ne partagez jamais vos clés API publiquement.

Si vous exposez accidentellement des clés API :
1. Régénérez toutes les clés API dans Prowlarr/Radarr/Sonarr
2. Reconfigurez via le Setup Wizard ou l'interface web
3. Redémarrez le container

Consultez [SECURITY_INCIDENT.md](SECURITY_INCIDENT.md) pour l'historique des incidents de sécurité.

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
docker-compose -f docker-compose.dev.yml up --build
```

---

## 📝 Licence

Licence MIT - Voir le fichier [LICENSE](LICENSE) pour plus de détails

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
