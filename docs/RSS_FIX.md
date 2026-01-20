# 🔧 Corrections URL RSS et qBittorrent - v2.5.1

## ✅ Problèmes Résolus

### 1. URL Torrent Incorrecte dans le Flux RSS

#### Symptôme
```json
{
  "link": "http://localhost:8000/torrents/data%2Ftorrents%2FThrough%20My%20Window.torrent"
}
```

L'URL contenait le chemin complet du fichier (`data/torrents/`) au lieu du nom seulement.

#### Cause
`torrent.py` retournait le chemin complet (`str(path)`) au lieu du nom de fichier seulement.

#### ✅ Solution

**Fichier `torrent.py`** :
```python
# AVANT (ligne 41 et 66)
return str(path)  # Retournait /app/data/torrents/nom.torrent

# APRÈS
return filename   # Retourne seulement nom.torrent
```

**Fichier `radarr_sonarr.py`** :
```python
# AJOUT : Import de TORRENT_DIR
from config import TORRENT_DIR

# MODIFICATION : Fonction is_download_id_imported()
def is_download_id_imported(torrent_file: str, imported_download_ids: Set[str]) -> bool:
    # Si c'est juste un nom de fichier, reconstruire le chemin complet
    if '/' not in torrent_file and '\\' not in torrent_file:
        torrent_file_path = str(TORRENT_DIR / torrent_file)
    else:
        torrent_file_path = torrent_file
    
    # ... reste du code
```

#### Résultat
```json
{
  "link": "http://localhost:8000/torrents/Through%20My%20Window.torrent"
}
```

URL propre et correcte ! ✅

---

### 2. qBittorrent Ne Peut Pas Accéder au Flux

#### Symptôme
- Flux RSS ajouté dans qBittorrent avec `http://localhost:8000/rss/torrent.json`
- qBittorrent ne trouve aucun torrent
- Aucune erreur visible

#### Cause
**Réseau Docker** : `localhost:8000` dans le conteneur qBittorrent pointe vers **son propre conteneur**, pas vers grab2rss.

#### ✅ Solution 1 : Utiliser le Nom du Conteneur

Dans qBittorrent, utiliser :
```
http://grab2rss:8000/rss/torrent.json
```

**Prérequis** : Les deux conteneurs doivent être sur le même réseau Docker.

#### ✅ Solution 2 : Configurer le Réseau Docker

Le `docker-compose.yml` de Grab2RSS crée déjà un réseau `media-network`.

**Connecter qBittorrent** :
```bash
# Option A : Connecter le conteneur existant
docker network connect media-network qbittorrent

# Option B : Modifier le docker-compose de qBittorrent
# Ajouter :
networks:
  - media-network

networks:
  media-network:
    external: true
```

**Tester** :
```bash
docker exec qbittorrent ping -c 3 grab2rss
```

---

## 📝 Fichiers Modifiés

### 1. `torrent.py`

**Changements** :
- Ligne 34 : Mise à jour de la docstring
- Ligne 41 : `return filename` au lieu de `return str(path)`
- Ligne 66 : `return filename` au lieu de `return str(path)`

**Impact** : Les URLs RSS sont maintenant correctes.

### 2. `radarr_sonarr.py`

**Changements** :
- Ligne 12 : Ajout `from config import TORRENT_DIR`
- Lignes 223-235 : Modification de `is_download_id_imported()` pour gérer les noms de fichiers

**Impact** : La vérification Radarr/Sonarr fonctionne toujours correctement.

### 3. `docker-compose.yml`

**Déjà configuré** :
- Réseau `media-network` créé automatiquement
- Grab2RSS connecté au réseau

**Aucune modification nécessaire** si vous utilisez le fichier fourni.

---

## 🧪 Tests de Validation

### Test 1 : URL RSS Correcte

```bash
# Tester le flux JSON
curl http://localhost:8000/rss/torrent.json | jq '.items[0].link'

# Résultat attendu :
"http://localhost:8000/torrents/Through%20My%20Window%202022%20MULTi%201080p%20WEB%20x264-STRINGERBELL.torrent"

# ✅ Pas de "data%2Ftorrents" dans l'URL
```

### Test 2 : Téléchargement Direct du Torrent

```bash
# Tester le téléchargement d'un torrent
curl -I "http://localhost:8000/torrents/Through%20My%20Window%202022%20MULTi%201080p%20WEB%20x264-STRINGERBELL.torrent"

# Résultat attendu :
HTTP/1.1 200 OK
Content-Type: application/x-bittorrent
```

### Test 3 : Connectivité Docker

```bash
# Vérifier que qBittorrent peut pinguer grab2rss
docker exec qbittorrent ping -c 3 grab2rss

# Résultat attendu :
3 packets transmitted, 3 received, 0% packet loss
```

### Test 4 : Accès au Flux depuis qBittorrent

```bash
# Depuis le conteneur qBittorrent
docker exec qbittorrent wget -O- http://grab2rss:8000/rss/torrent.json | head -20

# Résultat attendu :
{
  "version": "0.1",
  "name": "Grab2RSS",
  ...
}
```

---

## 📋 Migration depuis v2.5

### Étape 1 : Sauvegarder

```bash
# Sauvegarder l'ancienne version
cp torrent.py torrent.py.backup
cp radarr_sonarr.py radarr_sonarr.py.backup
```

### Étape 2 : Remplacer les Fichiers

```bash
# Copier les nouveaux fichiers
# torrent.py (MODIFIÉ)
# radarr_sonarr.py (MODIFIÉ)
```

### Étape 3 : Redémarrer

```bash
# Docker
docker compose down
docker compose up -d --build

# Manuel
# CTRL+C puis
python main.py
```

### Étape 4 : Vérifier

```bash
# 1. URL RSS correcte
curl http://localhost:8000/rss/torrent.json | jq '.items[0].link'

# 2. Pas de "data%2Ftorrents" ✅

# 3. Connecter qBittorrent au réseau
docker network connect media-network qbittorrent

# 4. Tester dans qBittorrent
# URL : http://grab2rss:8000/rss/torrent.json
```

---

## 🎯 Configuration qBittorrent Finale

### Flux RSS

```
URL : http://grab2rss:8000/rss/torrent.json
Nom : Grab2RSS - Tous les Trackers
Actualisation automatique : ✅
Intervalle : 30 minutes
```

### Règle de Téléchargement

```
Nom : Auto Seeding Grab2RSS
Doit contenir : (vide ou .torrent)
Catégorie : Seeding
Sauvegarder dans : /downloads/seeding/
État : Démarrer le torrent
✅ Activer la règle
```

---

## ✅ Résultat Final

### Flux RSS JSON
```json
{
  "version": "0.1",
  "name": "Grab2RSS",
  "items": [
    {
      "id": "grab-1",
      "title": "Through My Window 2022 MULTi 1080p WEB x264-STRINGERBELL",
      "pubDate": "2026-01-19T17:06:04Z",
      "link": "http://localhost:8000/torrents/Through%20My%20Window%202022%20MULTi%201080p%20WEB%20x264-STRINGERBELL.torrent",
      "torrent": "http://localhost:8000/torrents/Through%20My%20Window%202022%20MULTi%201080p%20WEB%20x264-STRINGERBELL.torrent",
      "tracker": "Sharewood",
      "magnetLink": null
    }
  ]
}
```

### qBittorrent

```
Lecteur RSS
└── Grab2RSS - Tous les Trackers
    └── Through My Window 2022... ✅ Téléchargement 45%
    └── Predator Badlands 2025... ✅ Téléchargement 78%
    └── Tehran S03E01... ✅ Seed
```

---

## 💡 Rappels Importants

1. **Réseau Docker** : qBittorrent et Grab2RSS doivent être sur le même réseau
2. **URL correcte** : `http://grab2rss:8000` (pas `localhost`)
3. **Patience** : Le flux RSS se rafraîchit toutes les 30 minutes
4. **Logs** : Vérifier `docker compose logs -f grab2rss` si problème

---

## 🆘 Dépannage Rapide

| Problème | Solution |
|----------|----------|
| URL avec `data%2Ftorrents` | Utilisez les nouveaux fichiers torrent.py et radarr_sonarr.py |
| qBittorrent ne voit pas le flux | Connecter au réseau : `docker network connect media-network qbittorrent` |
| Flux vide dans qBittorrent | Vérifier qu'il y a des grabs : `curl http://localhost:8000/api/stats` |
| Torrents ne se téléchargent pas | Vérifier la règle de téléchargement dans qBittorrent |

---

**Version** : 2.5.1  
**Date** : 19 janvier 2026  
**Statut** : ✅ URLS RSS CORRIGÉES + GUIDE QBITTORRENT COMPLET
