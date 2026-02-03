# 📦 Guide d'Installation - Grab2RSS

## 🎯 Installation Rapide (Docker)

### Prérequis

- Docker >= 20.10
- Docker Compose >= 1.29
- Prowlarr installé et configuré

### Étape 1 : Créer le fichier docker-compose.yml

```bash
mkdir grab2rss && cd grab2rss
```

Créez un fichier `docker-compose.yml` (exemple dans `docker/docker-compose.example.yml`) :

```yaml
version: "3.8"

services:
  grab2rss:
    image: ghcr.io/kesurof/grabb2rss:latest
    container_name: grab2rss
    environment:
      - PUID=1000  # Votre User ID (id -u)
      - PGID=1000  # Votre Group ID (id -g)
      - TZ=Europe/Paris
    volumes:
      - ./config:/config
      - ./data:/app/data
    ports:
      - "8000:8000"
    restart: unless-stopped
```

### Étape 2 : Démarrage

```bash
# Démarrer le container
docker-compose up -d

# Vérifier les logs
docker-compose logs -f grab2rss
```

### Étape 3 : Configuration via le Setup Wizard

Ouvrez votre navigateur sur **http://localhost:8000**

Vous serez automatiquement redirigé vers le **Setup Wizard** où vous pourrez configurer :

1. **Prowlarr** (obligatoire) :
   - URL : `http://prowlarr:9696` (ou votre URL)
   - Clé API : obtenue depuis Prowlarr → Settings → General → API Key

2. **Radarr** (optionnel) :
   - URL : `http://radarr:7878`
   - Clé API : obtenue depuis Radarr → Settings → General → API Key

3. **Sonarr** (optionnel) :
   - URL : `http://sonarr:8989`
   - Clé API : obtenue depuis Sonarr → Settings → General → API Key

4. **Paramètres de synchronisation** :
   - Intervalle : 3600 secondes (1 heure)
   - Rétention : 168 heures (7 jours)
   - Déduplication : 168 heures

5. **Paramètres RSS** :
   - Domaine : localhost:8000 (ou votre domaine)
   - Protocole : http (ou https si derrière un proxy)

**C'est tout !** La configuration est sauvegardée dans `./config/settings.yml`

### Vérifier le statut
docker-compose ps
```

### Étape 4 : Vérification

```bash
# Test healthcheck
curl http://localhost:8000/health

# Ouvrir l'interface web
# Naviguer vers : http://votre-ip:8000
```

---

## 🔐 Obtenir la Clé API Prowlarr

### Méthode 1 : Via l'Interface Web

1. Ouvrir Prowlarr dans votre navigateur
2. Aller dans **Settings** (⚙️ en bas à gauche)
3. Onglet **General**
4. Section **Security**
5. Copier la **API Key**
6. Coller dans `PROWLARR_API_KEY` de votre fichier `settings.yml`

### Méthode 2 : Via le Fichier de Config

```bash
# Prowlarr stocke la clé dans config.xml
cat ~/.config/Prowlarr/config.xml | grep ApiKey
```

---

## 🌐 Configuration Réseau

### Prowlarr sur le Même Serveur

```env
PROWLARR_URL=http://localhost:9696
```

### Prowlarr sur un Autre Serveur

```env
PROWLARR_URL=http://192.168.1.10:9696
```

### Prowlarr dans Docker (Même Réseau)

```env
PROWLARR_URL=http://prowlarr:9696
```

Vérifier que les containers sont sur le même réseau :

```yaml
# docker-compose.yml
networks:
  media-network:
    external: true
```

### Derrière un Reverse Proxy

```env
RSS_DOMAIN=grab2rss.example.com
RSS_SCHEME=https
```

---

## 🔧 Configuration Avancée

### Personnaliser l'Intervalle de Sync

```env
# Sync toutes les 30 minutes
SYNC_INTERVAL=1800

# Sync toutes les 2 heures
SYNC_INTERVAL=7200

# Sync toutes les 6 heures
SYNC_INTERVAL=21600
```

### Configurer la Rétention

```env
# Garder 7 jours (recommandé)
RETENTION_HOURS=168

# Garder 14 jours
RETENTION_HOURS=336

# Garder 30 jours
RETENTION_HOURS=720

# Garder indéfiniment
RETENTION_HOURS=0
AUTO_PURGE=false
```

### Ajuster la Déduplication

```env
# Fenêtre de 24h (par défaut)
DEDUP_HOURS=24

# Fenêtre de 7 jours (recommandé)
DEDUP_HOURS=168

# Fenêtre de 30 jours
DEDUP_HOURS=720
```

### Optimiser les Performances

```env
# Récupérer moins d'enregistrements par sync (plus rapide)
PROWLARR_HISTORY_PAGE_SIZE=50

# Récupérer plus d'enregistrements (moins de syncs manquées)
PROWLARR_HISTORY_PAGE_SIZE=200
```

---

## 🐳 Configuration Docker Avancée

### Docker Compose Personnalisé

```yaml
version: '3.9'

services:
  grab2rss:
    build: .
    container_name: grab2rss
    ports:
      - "8000:8000"
    environment:
      - PROWLARR_URL=http://prowlarr:9696
      - PROWLARR_API_KEY=${PROWLARR_API_KEY}
      - SYNC_INTERVAL=3600
      - RETENTION_HOURS=168
      - AUTO_PURGE=true
      - DEDUP_HOURS=168
      - RSS_DOMAIN=grab2rss.local
      - RSS_SCHEME=http
    volumes:
      - ./data:/app/data
    networks:
      - media-network
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
    labels:
      - "com.centurylinklabs.watchtower.enable=true"

networks:
  media-network:
    external: true
```

### Build avec Variables d'Environnement

```bash
# Définir les variables
export PROWLARR_API_KEY="votre_clé"

# Build et lancer
docker-compose up -d

# Ou en une ligne
PROWLARR_API_KEY="votre_clé" docker-compose up -d
```

---

## 🔄 Mise à Jour

### Docker

```bash
cd /opt/grab2rss

# Arrêter
docker-compose down

# Mettre à jour le code
git pull
# OU télécharger la nouvelle version

# Rebuild
docker-compose build --no-cache

# Redémarrer
docker-compose up -d

# Vérifier
docker-compose logs -f grab2rss
```

---

## 🧪 Tests Post-Installation

### Test 1 : Healthcheck

```bash
curl http://localhost:8000/health | jq
```

**Résultat attendu** :
```json
{
  "status": "ok",
  "components": {
    "database": "ok",
    "prowlarr": "ok",
    "scheduler": "ok"
  }
}
```

### Test 2 : API Stats

```bash
curl http://localhost:8000/api/stats | jq
```

**Résultat attendu** :
```json
{
  "total_grabs": 0,
  "latest_grab": null,
  "storage_size_mb": 0,
  "tracker_stats": []
}
```

### Test 3 : Flux RSS

```bash
curl http://localhost:8000/rss | head -30
```

**Résultat attendu** : XML valide commençant par `<?xml version="1.0"?>`

### Test 4 : Interface Web

Ouvrir dans un navigateur :
```
http://localhost:8000
```

Vérifier :
- ✅ Dashboard affiche "0 grabs"
- ✅ Statut Sync : "Actif"
- ✅ Aucune erreur JavaScript (F12)

---

## 🚦 Démarrage Automatique

### Docker Auto-Restart

Déjà configuré dans `docker-compose.yml` :

```yaml
restart: unless-stopped
```

---

## 🔍 Vérification Post-Installation

### Checklist

- [ ] Docker et Docker Compose installés
- [ ] `docker-compose.yml` créé avec volumes `./config` et `./data`
- [ ] Container démarré sans erreur
- [ ] Setup Wizard terminé (Prowlarr configuré, clé API renseignée)
- [ ] Healthcheck retourne `status: ok`
- [ ] Interface Web accessible
- [ ] Première sync effectuée

---

## 🆘 Problèmes Courants

### Erreur : "PROWLARR_API_KEY manquante"

**Solution** : Vérifier que la clé est bien définie dans `settings.yml`

```bash
grep PROWLARR_API_KEY settings.yml
```

### Erreur : "Connection refused" (Prowlarr)

**Solution** : Vérifier que Prowlarr est accessible

```bash
curl http://prowlarr:9696  # ou localhost:9696
```

### Erreur : "Permission denied" (data/)

**Solution** : Corriger les permissions

```bash
chmod -R 755 data/
chmod -R 777 data/torrents/
```

### Interface Web : Page Blanche

**Solution** :
1. Ouvrir en navigation privée
2. Désactiver les extensions
3. Vérifier la console (F12)

### Plus de Solutions

Consultez [TROUBLESHOOTING.md](TROUBLESHOOTING.md) pour un guide complet.

---

## 📞 Support

Pour toute question ou problème :

1. Vérifier [TROUBLESHOOTING.md](TROUBLESHOOTING.md)
2. Consulter les logs : `docker-compose logs -f`
3. Tester le healthcheck : `curl http://localhost:8000/health`
4. Ouvrir une issue sur GitHub

---

**Installation réussie ! 🎉**

Interface Web : `http://localhost:8000`
