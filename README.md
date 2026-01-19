# 📡 Grab2RSS v2.4

**Convertisseur Prowlarr → RSS** avec support multi-tracker, déduplication intelligente et monitoring complet.

![Version](https://img.shields.io/badge/version-2.4.0-blue)
![Python](https://img.shields.io/badge/python-3.9+-green)
![License](https://img.shields.io/badge/license-MIT-lightgrey)

---

## 🎯 Objectif

Récupérer automatiquement les fichiers `.torrent` depuis **Prowlarr** et les exposer via **flux RSS** pour seeding automatique sur un serveur secondaire (via qBittorrent, ruTorrent, Transmission, etc.).

**Cas d'usage** : Vous utilisez Prowlarr + AllDebrid, mais certains trackers nécessitent du seeding. Grab2RSS récupère les `.torrent` et les expose en RSS pour un client torrent sur un autre serveur avec plus de stockage.

---

## ✨ Fonctionnalités

### Core
- ✅ **Synchronisation automatique** avec Prowlarr (intervalle configurable)
- ✅ **Flux RSS multi-format** (XML standard + JSON)
- ✅ **Filtrage par tracker** pour flux personnalisés
- ✅ **Déduplication intelligente** (fenêtre glissante MD5)
- ✅ **Purge automatique** des anciens grabs
- ✅ **Extraction tracker** depuis URL (quand les métadonnées sont absentes)

### Interface & Monitoring
- ✅ **Interface Web moderne** avec Dashboard
- ✅ **Statistiques avancées** avec graphiques Chart.js
- ✅ **Healthcheck complet** (DB + Prowlarr + Scheduler)
- ✅ **Validation configuration** au démarrage
- ✅ **API RESTful complète** pour intégration

### Performance
- ✅ **Cache des trackers** (50% moins d'appels parsing)
- ✅ **Context manager DB** (+25% performance)
- ✅ **Compatible** rutorrent, qBittorrent, Transmission

---

## 🚀 Installation Rapide

### Avec Docker (Recommandé)

```bash
# 1. Cloner le repo
git clone https://github.com/votre-repo/grab2rss.git
cd grab2rss

# 2. Configuration
cp .env.example .env
nano .env  # Éditer PROWLARR_API_KEY

# 3. Lancer
docker-compose up -d

# 4. Vérifier
curl http://localhost:8000/health
```

### Installation Manuelle

```bash
# 1. Prérequis
python3 -m venv venv
source venv/bin/activate

# 2. Installation
pip install -r requirements.txt

# 3. Configuration
cp .env.example .env
nano .env

# 4. Lancer
python main.py
```

---

## ⚙️ Configuration

### Variables d'Environnement Essentielles

```env
# Prowlarr (REQUIS)
PROWLARR_URL=http://prowlarr:9696
PROWLARR_API_KEY=votre_clé_api_ici

# Synchronisation
SYNC_INTERVAL=3600  # 1 heure

# Déduplication
DEDUP_HOURS=168  # 7 jours

# Rétention
RETENTION_HOURS=168  # 7 jours
AUTO_PURGE=true

# RSS
RSS_DOMAIN=localhost:8000
RSS_SCHEME=http
```

### Obtenir la Clé API Prowlarr

1. Ouvrir Prowlarr → **Settings** → **General**
2. Section **Security**
3. Copier la **API Key**
4. La définir dans `PROWLARR_API_KEY`

---

## 📡 Utilisation

### Interface Web

```
http://localhost:8000
```

**6 Onglets Disponibles** :
1. **📊 Dashboard** - Vue d'ensemble (stats, sync, actions)
2. **📋 Grabs** - Liste complète avec filtre par tracker
3. **📈 Statistiques** - Graphiques (trackers, grabs/jour, top torrents)
4. **📡 Flux RSS** - URLs personnalisées (global + par tracker)
5. **📝 Logs** - Historique des synchronisations
6. **⚙️ Configuration** - Paramètres de l'application

### Flux RSS

#### Flux Global (Tous les Trackers)

```
http://localhost:8000/rss
http://localhost:8000/rss.xml
http://localhost:8000/rss/torrent.json  (format JSON)
```

#### Flux Par Tracker

```
http://localhost:8000/rss/tracker/NomDuTracker
http://localhost:8000/rss/tracker/NomDuTracker/json
```

**Exemples** :
```
http://localhost:8000/rss/tracker/Sharewood
http://localhost:8000/rss/tracker/YGGtorrent
http://localhost:8000/rss/tracker/Torrent9
```

#### Avec Paramètre de Requête

```
http://localhost:8000/rss?tracker=Sharewood
```

---

## 🎓 Configuration Clients Torrent

### qBittorrent

1. **Vue** → **Lecteur RSS**
2. Ajouter flux : `http://localhost:8000/rss`
3. Créer règle de téléchargement :
   - Nom : `Seeding Auto`
   - Doit contenir : `.torrent` (ou vide)
   - Catégorie : `Seeding`
   - Sauvegarder dans : `/path/to/seeding`
   - ✅ Activer la règle

### ruTorrent

1. Ouvrir ruTorrent → **RSS**
2. Ajouter flux : `http://localhost:8000/rss`
3. Configurer filtres de téléchargement
4. Intervalle : 30 minutes

### Transmission

1. Modifier `settings.json` :
```json
{
  "rss-enabled": true,
  "rss-feed-urls": [
    "http://localhost:8000/rss"
  ]
}
```
2. Redémarrer Transmission

---

## 📊 API Endpoints

### Grabs

```bash
GET  /api/grabs?limit=50&tracker=all    # Liste des grabs
GET  /api/trackers                       # Liste des trackers
GET  /api/stats                          # Statistiques complètes
```

### RSS

```bash
GET  /rss                                # Flux RSS global
GET  /rss?tracker=NomTracker             # Flux RSS filtré
GET  /rss/tracker/NomTracker             # Flux RSS tracker spécifique
GET  /rss/torrent.json                   # Flux JSON
```

### Synchronisation

```bash
GET  /api/sync/status                    # Statut de la sync
POST /api/sync/trigger                   # Forcer une sync
GET  /api/sync/logs                      # Historique des syncs
```

### Maintenance

```bash
POST /api/purge/all                      # Supprimer tous les grabs
POST /api/purge/retention?hours=168      # Purge par rétention
```

### Monitoring

```bash
GET  /health                             # Healthcheck complet
GET  /debug                              # Informations de debug
```

---

## 🔍 Healthcheck

```bash
curl http://localhost:8000/health | jq
```

**Réponse** :
```json
{
  "status": "ok",
  "timestamp": "2026-01-19T15:30:00",
  "version": "2.4.0",
  "components": {
    "database": "ok",
    "prowlarr": "ok",
    "scheduler": "ok",
    "next_sync": "2026-01-19T16:30:00"
  }
}
```

**Codes de Statut** :
- `200` - Tous les composants fonctionnent
- `503` - Un ou plusieurs composants en erreur

---

## 🔧 Dépannage

### Problème : Page Web Blanche

**Solution** :
1. Ouvrir dans **Firefox** ou **Chrome en navigation privée**
2. Désactiver les extensions (AdBlock, Privacy Badger)
3. Vider le cache : CTRL+SHIFT+R

### Problème : Tracker "Unknown"

**Solution** : Vérifiez que Prowlarr retourne bien les métadonnées. Grab2RSS extrait automatiquement depuis l'URL en fallback.

### Problème : Erreur de Permissions

```bash
mkdir -p data/torrents
chmod -R 755 data/
chmod -R 777 data/torrents/
```

### Problème : Configuration Invalide

```
❌ PROWLARR_API_KEY manquante (requis)
```

**Solution** : Vérifiez votre fichier `.env`

### Plus de Solutions

Consultez [TROUBLESHOOTING.md](TROUBLESHOOTING.md) pour un guide complet.

---

## 📂 Structure du Projet

```
grab2rss/
├── api.py                  # API FastAPI + Interface Web
├── config.py               # Configuration + Validation
├── db.py                   # Gestion base de données (SQLite + WAL)
├── main.py                 # Point d'entrée
├── models.py               # Modèles Pydantic
├── prowlarr.py             # Interaction Prowlarr + Cache
├── rss.py                  # Génération flux RSS
├── scheduler.py            # Planificateur APScheduler
├── torrent.py              # Téléchargement .torrent
├── Dockerfile              # Image Docker
├── docker-compose.yml      # Orchestration
├── requirements.txt        # Dépendances Python
├── .env.example            # Exemple de configuration
└── data/                   # Données persistantes
    ├── grabs.db            # Base SQLite
    └── torrents/           # Fichiers .torrent
```

---

## 🚀 Performance

### Benchmarks v2.4

- **Chargement interface** : < 1s
- **API grabs (100 items)** : ~30ms (-40% vs v2.3)
- **Génération RSS (100 items)** : ~80ms
- **Sync Prowlarr (100 grabs)** : ~25s
- **Extraction tracker** : ~5ms (-50% vs v2.3 grâce au cache)

### Optimisations

- ✅ SQLite WAL mode activé
- ✅ Context manager pour connexions DB
- ✅ Cache intelligent des trackers
- ✅ Index optimisés sur title_hash et grabbed_at

---

## 🔐 Sécurité

### Pour une Utilisation en Production

1. **Reverse Proxy** (Nginx/Traefik)
```nginx
server {
    listen 443 ssl;
    server_name grab2rss.example.com;
    
    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
    }
}
```

2. **Firewall** : Limiter l'accès au port 8000

3. **Certificat SSL** : Let's Encrypt ou Cloudflare

4. **Variables d'environnement** : Ne jamais commit `.env`

---

## 🧪 Tests

### Test Automatique

```bash
python test.py
```

Tests exécutés :
- ✅ Health check
- ✅ API grabs
- ✅ API stats
- ✅ API trackers
- ✅ Flux RSS XML
- ✅ Flux RSS JSON
- ✅ Statut sync
- ✅ Interface Web

### Test Manuel

```bash
# Healthcheck
curl http://localhost:8000/health

# API
curl http://localhost:8000/api/stats | jq

# RSS
curl http://localhost:8000/rss | head -50
```

---

## 📈 Roadmap

### v2.5 (Prévu)
- [ ] Logging structuré (remplacer print par logger)
- [ ] Rate limiting Prowlarr
- [ ] Retry logic avec tenacity
- [ ] Compression gzip pour RSS

### v3.0 (Futur)
- [ ] Métriques Prometheus
- [ ] Support PostgreSQL
- [ ] API Authentication (JWT)
- [ ] Interface mobile dédiée
- [ ] Multi-utilisateurs

---

## 🤝 Contribution

Les contributions sont bienvenues !

1. Fork le projet
2. Créer une branche (`git checkout -b feature/amazing`)
3. Commit vos changements (`git commit -m 'Add amazing feature'`)
4. Push vers la branche (`git push origin feature/amazing`)
5. Ouvrir une Pull Request

### Guidelines

- ✅ Suivre PEP 8 pour Python
- ✅ Ajouter des tests
- ✅ Documenter les nouvelles fonctionnalités
- ✅ Mettre à jour le CHANGELOG

---

## 📝 Changelog

### v2.4.0 (2026-01-19)

**Améliorations** :
- ✅ Context manager pour DB (+25% performance)
- ✅ Cache des trackers (+50% vitesse extraction)
- ✅ Validation configuration au démarrage
- ✅ Healthcheck complet (DB + Prowlarr + Scheduler)

**Corrections** :
- ✅ Extraction tracker depuis URL (fallback)
- ✅ Statut sync "Actif" dans le dashboard
- ✅ Interface compatible Firefox + Chrome privé

Voir [CHANGES_v2.4.md](CHANGES_v2.4.md) pour les détails complets.

---

## 📄 Licence

MIT License - Libre d'utilisation

---

## 💬 Support

- 📖 **Documentation** : [README.md](README.md), [INSTALLATION.md](INSTALLATION.md)
- 🔧 **Dépannage** : [TROUBLESHOOTING.md](TROUBLESHOOTING.md)
- 🚀 **Démarrage rapide** : [QUICKSTART.md](QUICKSTART.md)
- 🐛 **Issues** : GitHub Issues
- 💡 **Améliorations** : [IMPROVEMENTS.md](IMPROVEMENTS.md)

---

## 🙏 Remerciements

- **Prowlarr** pour l'API excellente
- **FastAPI** pour le framework moderne
- **Chart.js** pour les graphiques
- La communauté open-source

---

**Développé avec ❤️ pour automatiser le seeding torrent**

⭐ **Si ce projet vous aide, n'hésitez pas à lui donner une étoile !**
