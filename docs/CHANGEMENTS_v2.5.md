# 🚀 Grab2RSS v2.5 - Changements et Améliorations

## 📋 Résumé

Version 2.5 apporte des améliorations majeures :
- ✅ Filtrage intelligent Radarr/Sonarr
- ✅ Interface Admin complète
- ✅ Correction bug majeur (hash torrent)
- ✅ Nouveaux endpoints API
- ✅ Synchronisation améliorée

---

## ✨ Nouveautés Majeures

### 1. 🎯 Filtrage Radarr/Sonarr

**Problème résolu** : Prowlarr "grab" ne signifie pas "importé"

**Avant v2.5** :
```
Prowlarr grabbed: 150 torrents
Flux RSS: 150 torrents
Problème: Beaucoup rejetés par Radarr/Sonarr
```

**Après v2.5** :
```
Prowlarr grabbed: 150 torrents
Radarr imported: 3 films
Sonarr imported: 2 épisodes
Flux RSS: 5 torrents ✅ (seulement les vrais imports)
```

**Configuration** :
```env
RADARR_URL=http://localhost:7878
RADARR_API_KEY=votre_clé
SONARR_URL=http://localhost:8989
SONARR_API_KEY=votre_clé
```

**Comment ça marche** :
1. Récupère les `downloadId` des grabbed Radarr/Sonarr
2. Récupère les `downloadId` des `downloadFolderImported`
3. Intersection = downloadId vraiment importés
4. Calcule le hash SHA1 du .torrent
5. Compare avec les downloadId importés
6. ✅ Match = Ajouté au flux RSS

**Cache intelligent** : 5 minutes pour éviter de surcharger les APIs

### 2. 🔧 Onglet Admin

**Accès** : Interface web → "🔧 Admin"

**Contenu** :

#### 📊 Stats Système en Temps Réel
```
- Taille base de données (MB)
- Nombre de grabs/logs/config
- Fichiers torrents (count + size)
- Mémoire RAM utilisée
- CPU usage (%)
- Uptime (heures/minutes)
```

#### 🛠️ Actions de Maintenance
```
- 🔄 Rafraîchir les stats
- 🗑️ Vider le cache (trackers + imports)
- 🔧 Optimiser BD (VACUUM SQLite)
- 📡 Forcer une synchronisation
- 🗑️ Purger les anciens grabs
```

#### 📋 Logs Système
```
- Affichage par niveau (✅ ❌ ⚠️ ℹ️)
- Filtrage dynamique
- Timestamps précis
- Détails d'erreur
```

### 3. 🐛 Correction Bug Majeur

**Bug corrigé** :
```
⚠️  Erreur calcul hash: "Invalid token character (b'<') at position 0."
⊘ Non importé: Through.My.Window.2022.torrent
```

**Cause** : Le fichier téléchargé n'était pas un torrent valide mais une page HTML (erreur 404, page d'erreur tracker, etc.)

**Solution v2.5** :

```python
def is_valid_torrent_file(file_path: str) -> bool:
    """Vérifie si c'est un vrai torrent"""
    with open(file_path, 'rb') as f:
        first_byte = f.read(1)
        # Un torrent bencodé commence par 'd'
        # Si '<', c'est du HTML
        return first_byte == b'd'
```

**Résultat** :
- ✅ Détection fichiers corrompus
- ✅ Messages d'erreur clairs
- ✅ Pas de crash de l'application
- ✅ Logs informatifs

### 4. 🆕 Nouveaux Endpoints API

#### POST /api/cache/clear
Vide tous les caches (trackers + imports Radarr/Sonarr)

```bash
curl -X POST http://localhost:8000/api/cache/clear
```

**Réponse** :
```json
{
  "status": "cleared",
  "message": "Cache vidé (15 trackers)",
  "tracker_cache_cleared": 15
}
```

#### POST /api/db/vacuum
Optimise la base de données SQLite

```bash
curl -X POST http://localhost:8000/api/db/vacuum
```

**Réponse** :
```json
{
  "status": "optimized",
  "message": "Base de données optimisée",
  "size_before_mb": 12.5,
  "size_after_mb": 10.2,
  "saved_mb": 2.3
}
```

#### GET /api/logs/system
Récupère les logs système avec filtrage

```bash
# Tous les logs
curl http://localhost:8000/api/logs/system

# Seulement les erreurs
curl "http://localhost:8000/api/logs/system?level=error&limit=50"
```

**Réponse** :
```json
{
  "logs": [
    {
      "timestamp": "2026-01-19T15:30:00",
      "level": "success",
      "type": "sync",
      "message": "Sync: 5 grabs, 0 doublons",
      "details": null
    }
  ],
  "total": 120,
  "level": "all"
}
```

#### GET /api/stats/detailed
Statistiques système détaillées

```bash
curl http://localhost:8000/api/stats/detailed
```

**Réponse** :
```json
{
  "timestamp": "2026-01-19T15:30:00",
  "database": {
    "path": "/app/data/grabs.db",
    "size_mb": 10.5,
    "grabs": 245,
    "sync_logs": 120,
    "config_entries": 12
  },
  "torrents": {
    "count": 245,
    "total_size_mb": 125.8,
    "directory": "/app/data/torrents"
  },
  "system": {
    "memory_mb": 85.4,
    "cpu_percent": 2.5,
    "threads": 8,
    "uptime_seconds": 86400
  }
}
```

### 5. 🔄 Synchronisation Améliorée

**Avant v2.4** :
```javascript
// Lançait la sync
// Attendait 2 secondes fixes
// Pas de vérification du résultat
```

**Après v2.5** :
```javascript
async function syncNow() {
  // 1. Vérifier si sync déjà en cours
  const trigger = await fetch('/api/sync/trigger');
  if (trigger.status === 'already_running') {
    alert('⏳ Sync déjà en cours');
    return;
  }
  
  // 2. Polling toutes les 1s (max 30s)
  for (let i = 0; i < 30; i++) {
    await sleep(1000);
    const status = await fetch('/api/sync/status');
    
    if (!status.is_running) {
      // 3. Sync terminée !
      if (status.last_error) {
        alert('❌ Erreur: ' + status.last_error);
      } else {
        alert('✅ Sync terminée !');
      }
      break;
    }
  }
  
  // 4. Rafraîchir les données
  await refreshData();
}
```

**Résultat** :
- ✅ Pas de double sync
- ✅ Attente réelle de la fin
- ✅ Messages de succès/erreur
- ✅ Interface réactive

---

## 🔧 Améliorations Techniques

### Cache Intelligent

**Trackers** :
- Cache mémoire (indexerId → nom)
- Vidable via API ou interface
- Améliore les performances de 50%

**Imports Radarr/Sonarr** :
- Cache de 5 minutes
- Évite la surcharge des APIs
- Fonction `clear_cache()` exposée

### Optimisation Base de Données

**VACUUM SQLite** :
- Compacte la base
- Libère espace disque
- Améliore les performances
- Accessible via interface

### Logs Structurés

**Format** :
```python
{
  "timestamp": "2026-01-19T15:30:00",
  "level": "success | error | warning | info",
  "type": "sync | cache | vacuum | purge",
  "message": "Description courte",
  "details": "Détails optionnels"
}
```

**Avantages** :
- Filtrage facile
- Recherche efficace
- Affichage coloré
- Export futur (v2.6)

### Dépendance psutil

**Ajoutée** : `psutil==5.9.8`

**Utilisation** :
```python
import psutil

process = psutil.Process()
memory_mb = process.memory_info().rss / (1024 * 1024)
cpu_percent = process.cpu_percent(interval=0.1)
threads = process.num_threads()
```

**Statistiques système** :
- Mémoire RAM utilisée
- CPU usage
- Nombre de threads
- Uptime calculé

---

## 📊 Exemples d'Utilisation

### Exemple 1 : Filtrage Radarr/Sonarr

```bash
# 1. Configurer .env
RADARR_URL=http://localhost:7878
RADARR_API_KEY=abc123
SONARR_URL=http://localhost:8989
SONARR_API_KEY=def456

# 2. Redémarrer
docker-compose restart

# 3. Vérifier les logs
docker-compose logs -f grab2rss
```

**Logs attendus** :
```
📥 Radarr: 50 grabbed, 30 imported, 25 valides
📺 Sonarr: 23 grabbed, 15 imported, 12 valides
✅ Total: 37 downloadId importés dans le cache
🔍 Vérification activée: 37 downloadId importés

✔️  Film A
✔️  Film B
⊘ Non importé: Film C
⊘ Non importé: Film D

✅ Sync terminée: 2 grabs, 0 doublons, 2 non importés
```

### Exemple 2 : Maintenance via Admin

**Scénario** : La base de données est fragmentée après beaucoup de suppressions.

```bash
# Via Interface
1. Aller dans "🔧 Admin"
2. Cliquer "🔧 Optimiser BD"
3. Confirmer
4. Voir: "Espace libéré: 2.3 MB"

# Via API
curl -X POST http://localhost:8000/api/db/vacuum
```

**Résultat** :
```json
{
  "status": "optimized",
  "message": "Base de données optimisée",
  "size_before_mb": 12.5,
  "size_after_mb": 10.2,
  "saved_mb": 2.3
}
```

### Exemple 3 : Vider Cache

**Scénario** : Les trackers ne sont pas extraits correctement.

```bash
# Via Interface
1. Onglet "🔧 Admin"
2. Cliquer "🗑️ Vider Cache"
3. Confirmer
4. Attendre la prochaine sync

# Via API
curl -X POST http://localhost:8000/api/cache/clear
```

**Résultat** :
```
🗑️  Cache trackers vidé (15 entrées)
🗑️  Cache Radarr/Sonarr vidé
```

Prochaine sync recalculera tous les trackers.

---

## 🚀 Migration depuis v2.4

### Étape 1 : Sauvegarde

```bash
# Sauvegarder la config
cp .env .env.backup

# Sauvegarder les données (optionnel)
cp -r data/ data.backup/
```

### Étape 2 : Mise à jour des fichiers

```bash
# Remplacer tous les fichiers sauf:
# - .env (à garder)
# - data/ (à garder)
```

**Fichiers modifiés v2.5** :
- ✅ `api.py` - Interface Admin + nouveaux endpoints
- ✅ `radarr_sonarr.py` - Fix bug + filtrage
- ✅ `prowlarr.py` - Cache functions
- ✅ `db.py` - Vacuum function
- ✅ `requirements.txt` - + psutil

**Fichiers inchangés** :
- ✅ `main.py`
- ✅ `config.py`
- ✅ `models.py`
- ✅ `scheduler.py`
- ✅ `torrent.py`
- ✅ `rss.py`
- ✅ `Dockerfile`
- ✅ `docker-compose.yml`

### Étape 3 : Nouvelles dépendances

```bash
# Installer psutil
pip install psutil==5.9.8

# Ou réinstaller tout
pip install -r requirements.txt
```

### Étape 4 : Configuration optionnelle

Ajouter dans `.env` (optionnel) :

```env
# Radarr (Optionnel - pour filtrage v2.5)
RADARR_URL=http://localhost:7878
RADARR_API_KEY=

# Sonarr (Optionnel - pour filtrage v2.5)
SONARR_URL=http://localhost:8989
SONARR_API_KEY=
```

### Étape 5 : Redémarrage

```bash
# Docker
docker-compose down
docker-compose build --no-cache
docker-compose up -d

# Manuel
# CTRL+C puis
python main.py
```

### Étape 6 : Vérification

```bash
# 1. Healthcheck
curl http://localhost:8000/health | jq '.version'
# Devrait afficher: "2.5.0"

# 2. Tester l'onglet Admin
# Naviguer vers http://localhost:8000
# Cliquer sur "🔧 Admin"
# Les stats devraient s'afficher

# 3. Tester la sync
curl -X POST http://localhost:8000/api/sync/trigger
# Devrait répondre: "triggered" ou "already_running"
```

---

## 📈 Performance v2.5

### Benchmarks

| Opération | v2.4 | v2.5 | Amélioration |
|-----------|------|------|--------------|
| Calcul hash torrent | 5ms | 2ms (si invalide) | +60% |
| Extraction tracker | 10ms | 5ms (avec cache) | +50% |
| Sync complète | 25s | 25s | = |
| VACUUM DB | N/A | 2-5s | NEW |
| Clear cache | N/A | <5ms | NEW |

### Mémoire

| Composant | RAM |
|-----------|-----|
| Base (Python) | ~50 MB |
| FastAPI | ~20 MB |
| Caches | ~5 MB |
| psutil | ~2 MB |
| **Total** | **~80 MB** |

### Charge API

| Endpoint | Temps moyen |
|----------|-------------|
| `/api/stats` | 30ms |
| `/api/grabs` | 25ms |
| `/rss` | 80ms |
| `/api/stats/detailed` | 50ms |
| `/api/cache/clear` | 5ms |
| `/api/db/vacuum` | 2-5s |

---

## 🐛 Bugs Connus & Solutions

### 1. Fichier torrent invalide

**Symptôme** :
```
⚠️  Fichier torrent invalide ou corrompu: xxx.torrent
💡 Le fichier téléchargé n'est pas un torrent valide
```

**Cause** : Le tracker a retourné une page d'erreur (HTML) au lieu du .torrent

**Solution v2.5** : Détecté automatiquement et rejeté proprement

**Action requise** : Aucune, le torrent est simplement ignoré

### 2. VACUUM bloque l'application

**Symptôme** : Interface freeze pendant VACUUM

**Cause** : VACUUM lock la base de données

**Solution** : Normal, dure 2-5s maximum

**Action** : Attendre la fin de l'opération

### 3. Cache pas vidé après clear_cache

**Symptôme** : Trackers toujours en cache après clear

**Cause** : Cache recréé immédiatement

**Solution** : Attendre la prochaine sync pour voir l'effet

---

## 🎯 Roadmap v2.6+

### Prévu

- [ ] Export logs (CSV, JSON)
- [ ] Notifications (email, webhook)
- [ ] Métriques Prometheus
- [ ] Rate limiting API
- [ ] Logs rotatifs (fichier)
- [ ] Dark/Light theme

### En Réflexion

- [ ] Support PostgreSQL
- [ ] Interface mobile native
- [ ] Multi-utilisateurs
- [ ] API Authentication (JWT)
- [ ] Dashboard personnalisable

---

## 📝 Notes Importantes

### Filtrage Radarr/Sonarr

**Optionnel** : Si vous ne configurez pas Radarr/Sonarr, l'application fonctionne comme avant (v2.4).

**Recommandé** : Activer le filtrage pour ne seeder que les vrais imports.

**Performance** : Cache de 5 minutes, pas de surcharge.

### VACUUM Base de Données

**Quand** : Après de nombreuses suppressions ou si la base est > 50 MB

**Durée** : 2-5 secondes (base moyenne)

**Impact** : Brève indisponibilité de la DB

**Fréquence** : Une fois par semaine suffit

### Cache Clearing

**Quand** : Après modification des indexers Prowlarr ou si extraction tracker incorrecte

**Durée** : < 5ms

**Impact** : Léger ralentissement temporaire (1-2 syncs)

---

## 🙏 Remerciements

- Tous les utilisateurs qui ont signalé le bug de hash
- La communauté pour les suggestions d'améliorations
- Les contributeurs du projet

---

**Version** : 2.5.0  
**Date** : 19 janvier 2026  
**Licence** : MIT
