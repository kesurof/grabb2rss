# 🔧 Configuration qBittorrent + Grab2RSS (Docker)

## ✅ Problème Résolu

Le problème venait de **deux choses** :

1. ✅ **URL incorrecte** : Le chemin complet était inclus (`data/torrents/...`)
2. ⚠️ **Réseau Docker** : qBittorrent ne peut pas accéder à `localhost:8000` depuis son conteneur

---

## 🐛 Problème 1 : URL Torrent Corrigée

### Avant (CASSÉ)
```json
{
  "link": "http://localhost:8000/torrents/data%2Ftorrents%2FThrough%20My%20Window.torrent"
}
```

### Après (CORRIGÉ)
```json
{
  "link": "http://localhost:8000/torrents/Through%20My%20Window.torrent"
}
```

**Fichiers corrigés** :
- `torrent.py` - Retourne seulement le nom du fichier
- `radarr_sonarr.py` - Reconstruit le chemin complet automatiquement

---

## 🌐 Problème 2 : Configuration Réseau Docker

### Diagnostic

Vos conteneurs Docker :
```
grab2rss     → Port 8000
qbittorrent  → Port 6881
```

**Problème** : `localhost:8000` dans qBittorrent pointe vers **son propre conteneur**, pas vers grab2rss.

### ✅ Solution A : Utiliser le Nom du Conteneur (RECOMMANDÉ)

Dans qBittorrent, utilisez l'URL :
```
http://grab2rss:8000/rss/torrent.json
```

**MAIS** cela nécessite que les deux conteneurs soient sur le **même réseau Docker**.

---

## 🔧 Configuration Docker Réseau

### Étape 1 : Créer un Réseau Docker Commun

```bash
# Créer un réseau
docker network create media-network

# Vérifier
docker network ls
```

### Étape 2 : Modifier docker-compose.yml de Grab2RSS

```yaml
version: '3.9'

services:
  grab2rss:
    build: .
    container_name: grab2rss
    ports:
      - "8000:8000"
    environment:
      - PROWLARR_URL=${PROWLARR_URL}
      - PROWLARR_API_KEY=${PROWLARR_API_KEY}
      # ... autres variables
    volumes:
      - ./data:/app/data
    networks:
      - media-network  # AJOUTÉ
    restart: unless-stopped

networks:
  media-network:
    external: true  # AJOUTÉ
```

### Étape 3 : Connecter qBittorrent au Réseau

**Option A** : Connecter le conteneur existant
```bash
docker network connect media-network qbittorrent
```

**Option B** : Modifier le docker-compose de qBittorrent
```yaml
version: '3.9'

services:
  qbittorrent:
    image: ghcr.io/linuxserver/qbittorrent:latest
    container_name: qbittorrent
    # ... votre config existante
    networks:
      - media-network  # AJOUTÉ
    restart: unless-stopped

networks:
  media-network:
    external: true  # AJOUTÉ
```

### Étape 4 : Redémarrer les Conteneurs

```bash
# Arrêter
docker compose down

# Relancer avec le nouveau réseau
docker compose up -d

# Vérifier la connectivité
docker exec qbittorrent ping -c 3 grab2rss
```

---

## 🎯 Configuration qBittorrent

### Étape 1 : Ajouter le Flux RSS

1. Ouvrir qBittorrent : `https://qbittorrent.kesurof.eu`
2. **Vue** → **Lecteur RSS**
3. Clic droit → **Ajouter un flux RSS**
4. URL : **`http://grab2rss:8000/rss/torrent.json`**
5. Nom : `Grab2RSS - Tous`
6. **Actualiser automatiquement** : ✅ Activé
7. Intervalle : `30 minutes`

### Étape 2 : Créer une Règle de Téléchargement

1. Clic droit sur le flux → **Règles de téléchargement**
2. Nouvelle règle :
   - **Nom** : `Auto Seeding Grab2RSS`
   - **Doit contenir** : `.torrent` (ou laisser vide)
   - **Catégorie** : `Seeding`
   - **Sauvegarder dans** : `/downloads/seeding/` (ou votre chemin)
   - **État après ajout** : Démarrer le torrent
   - ✅ **Activer la règle**
3. Cliquer **OK**

### Étape 3 : Tester

```bash
# Dans le conteneur qbittorrent, tester l'accès
docker exec qbittorrent wget -O- http://grab2rss:8000/rss/torrent.json

# Devrait afficher le JSON
```

---

## 🧪 Tests de Connectivité

### Test 1 : Depuis votre PC

```bash
# Tester l'URL
curl http://localhost:8000/rss/torrent.json | jq

# Vérifier l'URL du torrent (doit être correcte)
curl http://localhost:8000/rss/torrent.json | jq '.items[0].link'

# Devrait afficher :
# "http://localhost:8000/torrents/Through%20My%20Window.torrent"
# ET PAS : "http://localhost:8000/torrents/data%2Ftorrents%2F..."
```

### Test 2 : Depuis qBittorrent

```bash
# Entrer dans le conteneur qBittorrent
docker exec -it qbittorrent /bin/bash

# Tester l'accès à grab2rss
wget -O- http://grab2rss:8000/health

# Devrait afficher :
# {"status":"ok",...}

# Tester le flux RSS
wget -O- http://grab2rss:8000/rss/torrent.json | head -20
```

### Test 3 : Télécharger un Torrent

```bash
# Depuis votre PC, télécharger un torrent
curl -O http://localhost:8000/torrents/Through%20My%20Window.torrent

# Vérifier que c'est un torrent valide
file Through*.torrent

# Devrait afficher :
# Through My Window.torrent: BitTorrent file
```

---

## 📋 Checklist Complète

### Configuration Docker

- [ ] Réseau `media-network` créé
- [ ] `grab2rss` sur le réseau
- [ ] `qbittorrent` sur le réseau
- [ ] Conteneurs redémarrés
- [ ] Test ping : `docker exec qbittorrent ping grab2rss` fonctionne

### Configuration qBittorrent

- [ ] Flux RSS ajouté : `http://grab2rss:8000/rss/torrent.json`
- [ ] Actualisation automatique activée
- [ ] Règle de téléchargement créée
- [ ] Règle activée
- [ ] Test : Le flux apparaît dans qBittorrent

### Vérification Finale

- [ ] URL JSON correcte (sans `data%2Ftorrents`)
- [ ] qBittorrent peut accéder au flux
- [ ] Torrents se téléchargent automatiquement

---

## 🚀 Alternatives si Docker Réseau ne Fonctionne Pas

### Option 1 : Utiliser l'IP du Host

```bash
# Trouver l'IP du host Docker
ip addr show docker0 | grep inet

# Exemple : 172.17.0.1
```

Puis dans qBittorrent :
```
http://172.17.0.1:8000/rss/torrent.json
```

### Option 2 : Utiliser host.docker.internal

Dans qBittorrent :
```
http://host.docker.internal:8000/rss/torrent.json
```

**Note** : Fonctionne sur Docker Desktop (Windows/Mac), pas toujours sur Linux.

### Option 3 : Mode Réseau Host

Modifier `docker-compose.yml` :
```yaml
services:
  grab2rss:
    network_mode: "host"
    # Supprimer 'ports:' si vous utilisez network_mode: host
```

Puis dans qBittorrent :
```
http://localhost:8000/rss/torrent.json
```

**Attention** : `network_mode: host` expose tous les ports du conteneur.

---

## 🔍 Dépannage

### Problème : "Impossible de charger le flux RSS"

**Vérifier** :
```bash
# 1. Le conteneur grab2rss tourne
docker ps | grep grab2rss

# 2. L'API fonctionne
curl http://localhost:8000/health

# 3. Le JSON est valide
curl http://localhost:8000/rss/torrent.json | jq

# 4. qBittorrent peut accéder
docker exec qbittorrent wget -O- http://grab2rss:8000/health
```

### Problème : "Flux vide dans qBittorrent"

```bash
# Vérifier qu'il y a des grabs
curl http://localhost:8000/api/stats | jq '.total_grabs'

# Si 0, forcer une sync
curl -X POST http://localhost:8000/api/sync/trigger

# Attendre 30s puis vérifier
sleep 30
curl http://localhost:8000/api/stats | jq '.total_grabs'
```

### Problème : URL torrent toujours incorrecte

```bash
# Vérifier que vous utilisez les nouveaux fichiers
docker compose down
docker compose build --no-cache
docker compose up -d

# Tester l'URL
curl http://localhost:8000/rss/torrent.json | jq '.items[0].link'
```

---

## 📊 Architecture Réseau Finale

```
┌─────────────────────────────────────────────────┐
│               media-network                     │
│                                                 │
│  ┌──────────────┐         ┌──────────────┐     │
│  │   grab2rss   │ ←─────→ │ qbittorrent  │     │
│  │   :8000      │         │   :6881      │     │
│  └──────────────┘         └──────────────┘     │
│         ↓                         ↓             │
└─────────┼─────────────────────────┼─────────────┘
          │                         │
          ↓                         ↓
    Port 8000                   Port 6881
   (localhost)                 (localhost)
```

**Flux** :
1. Prowlarr → Grab2RSS (sync toutes les heures)
2. Grab2RSS → Flux RSS JSON
3. qBittorrent → Lit le flux RSS
4. qBittorrent → Télécharge les torrents automatiquement

---

## ✅ Résultat Attendu

### Dans qBittorrent

```
Lecteur RSS
└── Grab2RSS - Tous (http://grab2rss:8000/rss/torrent.json)
    └── Through My Window 2022 MULTi 1080p WEB x264-STRINGERBELL
    └── [Autres torrents...]
```

### Téléchargements Automatiques

```
Torrents
├── Through My Window 2022... (Téléchargement 45%)
├── Predator Badlands 2025... (Téléchargement 78%)
└── Tehran S03E01... (Seed)
```

---

## 💡 Conseils

1. **Patience** : Le flux RSS se met à jour toutes les 30 minutes
2. **Logs** : Vérifier les logs qBittorrent si problème
3. **Catégories** : Utilisez des catégories pour organiser
4. **Trackers** : Créez des flux par tracker si besoin

---

**Configuration terminée ! 🎉**

Votre qBittorrent devrait maintenant télécharger automatiquement tous les torrents de Grab2RSS.
