# 🚀 Guide de Démarrage Rapide - Grab2RSS v2.6+

## ⚡ Installation en 3 Minutes

### 🐳 Méthode Docker (Recommandée)

```bash
# 1. Créer le dossier
mkdir grab2rss && cd grab2rss

# 2. Créer docker-compose.yml
cat > docker-compose.yml << 'EOF'
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
    ports:
      - "8000:8000"
    restart: unless-stopped
EOF

# 3. Lancer
docker-compose up -d

# 4. Vérifier
curl http://localhost:8000/health
```

**C'est tout ! 🎉** Ouvrez `http://localhost:8000` et suivez le Setup Wizard.

---

## 🔑 Configuration via le Setup Wizard

Au premier lancement, vous serez automatiquement redirigé vers le **Setup Wizard** :

1. **Ouvrir** `http://localhost:8000` dans votre navigateur

2. **Prowlarr** (obligatoire) :
   - URL : `http://prowlarr:9696`
   - Clé API : obtenue depuis Prowlarr → Settings → General → API Key

3. **Radarr/Sonarr** (optionnels) :
   - Si vous voulez filtrer les grabs par films/séries
   - Mêmes paramètres : URL + Clé API

4. **Paramètres** :
   - Intervalle de sync : 3600 secondes (1 heure)
   - Rétention : 168 heures (7 jours)
   - Déduplication : 168 heures

5. **Cliquer sur "Sauvegarder"**

**Configuration sauvegardée** dans `./config/settings.yml` ✅

### 🔍 Où Trouver la Clé API Prowlarr ?

1. Ouvrir Prowlarr → **Settings** ⚙️
2. Onglet **General**
3. Section **Security**
4. Copier la **API Key**

---

## ✅ Vérifications

### Test 1 : Healthcheck

```bash
curl http://localhost:8000/health | jq
```

**Attendu** : `"status": "ok"`

### Test 2 : Interface Web

Ouvrir dans votre navigateur :
```
http://localhost:8000
```

Vous devriez voir le Dashboard avec 6 onglets.

### Test 3 : Première Sync

Le premier sync démarre automatiquement. Vérifiez les logs :

```bash
# Docker
docker-compose logs -f grab2rss

# Manuel
# Les logs s'affichent dans le terminal
```

Vous devriez voir :
```
⏱️  Sync Prowlarr en cours...
✔️  NomDuTorrent
✅ Sync terminée: X grabs, Y doublons
```

---

## 📡 Utiliser les Flux RSS

### Flux Global

```
http://localhost:8000/rss
```

Copiez cette URL dans votre client torrent (qBittorrent, ruTorrent, Transmission).

### Flux Par Tracker

```
http://localhost:8000/rss/tracker/Sharewood
http://localhost:8000/rss/tracker/YGGtorrent
```

Remplacez le nom du tracker selon vos besoins.

---

## 🎓 Configuration qBittorrent (Exemple)

### Étape 1 : Activer le Lecteur RSS

1. Ouvrir qBittorrent
2. **Vue** → **Lecteur RSS**
3. Le panneau RSS apparaît sur la gauche

### Étape 2 : Ajouter le Flux

1. Clic droit dans le panneau RSS
2. **Ajouter un flux RSS**
3. URL : `http://localhost:8000/rss`
4. Nom : `Grab2RSS - Tous`
5. Cliquer **OK**

### Étape 3 : Créer une Règle

1. Clic droit sur le flux → **Règles de téléchargement**
2. Créer une nouvelle règle
3. **Nom** : `Auto Seeding`
4. **Doit contenir** : `.torrent` (ou laisser vide)
5. **Catégorie** : `Seeding`
6. **Sauvegarder dans** : `/path/to/seeding`
7. ✅ **Activer la règle**
8. Cliquer **OK**

**C'est terminé !** Les torrents seront automatiquement téléchargés.

---

## 🔧 Commandes Utiles

### Démarrer/Arrêter

```bash
# Docker
docker-compose up -d      # Démarrer
docker-compose down       # Arrêter
docker-compose restart    # Redémarrer
docker-compose logs -f    # Voir les logs

# Manuel
python main.py            # Démarrer
# CTRL+C pour arrêter
```

### Forcer une Synchronisation

```bash
curl -X POST http://localhost:8000/api/sync/trigger
```

### Voir les Stats

```bash
curl http://localhost:8000/api/stats | jq
```

### Purger les Anciens Grabs

```bash
# Supprimer > 7 jours
curl -X POST "http://localhost:8000/api/purge/retention?hours=168"

# Tout supprimer
curl -X POST http://localhost:8000/api/purge/all
```

---

## 📊 Interface Web - Vue d'Ensemble

### 6 Onglets Disponibles

| Onglet | Description |
|--------|-------------|
| 📊 **Dashboard** | Stats globales, statut sync, actions rapides |
| 📋 **Grabs** | Liste complète avec filtre par tracker |
| 📈 **Statistiques** | Graphiques (trackers, activité, top torrents) |
| 📡 **Flux RSS** | URLs personnalisées pour chaque tracker |
| 📝 **Logs** | Historique des synchronisations |
| ⚙️ **Configuration** | Paramètres de l'application |

### Actions Rapides

- **🔄 Actualiser** : Rafraîchir les données
- **📡 Sync Maintenant** : Forcer une synchronisation
- **🗑️ Vider Tout** : Supprimer tous les grabs

---

## 🎯 Flux RSS Disponibles

### Format XML (Standard)

```
# Tous les trackers
http://localhost:8000/rss

# Tracker spécifique
http://localhost:8000/rss/tracker/Sharewood
http://localhost:8000/rss/tracker/YGGtorrent

# Avec filtre dans l'URL
http://localhost:8000/rss?tracker=Sharewood
```

### Format JSON

```
# Tous les trackers
http://localhost:8000/rss/torrent.json

# Tracker spécifique
http://localhost:8000/rss/tracker/Sharewood/json
```

### Compatibilité

✅ qBittorrent  
✅ ruTorrent  
✅ Transmission  
✅ Deluge  
✅ µTorrent  

---

## 💡 Astuces

### Astuce 1 : Réduire la Fenêtre de Déduplication

Si vous voyez beaucoup de doublons, modifiez via l'interface web (onglet Configuration) :

- **sync_dedup_hours** : `24` (au lieu de 168)

Ou éditez `/config/settings.yml` :
```yaml
sync:
  dedup_hours: 24
```

### Astuce 2 : Sync Plus Fréquente

Pour récupérer les torrents plus rapidement, modifiez via l'interface web :

- **sync_interval** : `1800` (30 minutes au lieu d'1h)

Ou éditez `/config/settings.yml` :
```yaml
sync:
  interval: 1800
```

### Astuce 3 : Garder Plus Longtemps

Pour garder les torrents plus de 7 jours, modifiez via l'interface web :

- **sync_retention_hours** : `720` (30 jours)

Ou éditez `/config/settings.yml` :
```yaml
sync:
  retention_hours: 720
```

### Astuce 4 : Flux RSS par Tracker

Créez plusieurs règles qBittorrent, une par tracker :

```
Règle 1 : http://localhost:8000/rss/tracker/Sharewood → Catégorie: Sharewood
Règle 2 : http://localhost:8000/rss/tracker/YGGtorrent → Catégorie: YGG
```

---

## 🐛 Problèmes Courants

### Problème : Page Blanche

**Solution rapide** :
1. Ouvrir en **navigation privée** (CTRL+SHIFT+N)
2. Essayer **Firefox** si vous êtes sur Chrome

### Problème : "Connection refused"

**Solution** :
```bash
# Vérifier que Prowlarr est accessible
curl http://localhost:9696
```

Si erreur, corriger `PROWLARR_URL` via l'interface web (onglet Configuration) ou en relançant le Setup Wizard

### Problème : Tracker "Unknown"

**C'est normal !** Grab2RSS extrait automatiquement le tracker depuis l'URL. Attendez la prochaine sync.

### Problème : Configuration Invalide

```
❌ PROWLARR_API_KEY manquante
```

**Solution** : Reconfigurer via l'interface web (onglet Configuration) ou relancer le Setup Wizard

Pour relancer le Setup Wizard :
```bash
docker-compose down
rm config/settings.yml
docker-compose up -d
```

---

## 📱 Accès Distant

### Depuis un Autre PC sur Votre Réseau

Remplacez `localhost` par l'IP du serveur :

```
http://192.168.1.10:8000
```

### Depuis Internet (Avancé)

1. Installer un reverse proxy (Nginx/Traefik)
2. Configurer un nom de domaine
3. Activer HTTPS avec Let's Encrypt

Voir [INSTALLATION.md](INSTALLATION.md) pour les détails.

---

## 🔍 Monitoring

### Healthcheck

```bash
# Status complet
curl http://localhost:8000/health | jq

# Simple check
curl -f http://localhost:8000/health && echo "OK" || echo "ERROR"
```

### Intégration Uptime Kuma

```
URL: http://localhost:8000/health
Method: GET
Expected: 200
Interval: 60 seconds
```

### Intégration Prometheus (Futur)

Endpoint metrics prévu dans v2.5.

---

## 🚀 Prochaines Étapes

Une fois que tout fonctionne :

1. **Configurer qBittorrent** pour télécharger automatiquement
2. **Ajuster SYNC_INTERVAL** selon vos besoins
3. **Créer des flux par tracker** si vous avez plusieurs sources
4. **Mettre en place un backup** de `data/grabs.db`
5. **Configurer un reverse proxy** si accès distant

---

## 📚 Documentation Complète

- 📖 [README.md](README.md) - Documentation principale
- 🔧 [INSTALLATION.md](INSTALLATION.md) - Installation détaillée
- 🐛 [TROUBLESHOOTING.md](TROUBLESHOOTING.md) - Résolution problèmes
- 📈 [IMPROVEMENTS.md](IMPROVEMENTS.md) - Améliorations futures
- 📝 [CHANGES_v2.4.md](CHANGES_v2.4.md) - Changelog détaillé

---

## 🎉 Félicitations !

Vous avez configuré Grab2RSS avec succès !

**Interface Web** : `http://localhost:8000`  
**Flux RSS** : `http://localhost:8000/rss`  
**Healthcheck** : `http://localhost:8000/health`

**Profitez de votre seeding automatisé ! 🌱**

---

## 💬 Besoin d'Aide ?

- 🔍 Consultez [TROUBLESHOOTING.md](TROUBLESHOOTING.md)
- 🐛 Ouvrez une issue sur GitHub
- 💬 Rejoignez la communauté

**Bon seeding ! 🚀**
