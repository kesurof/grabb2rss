# 🔧 FIX URGENT - Rebuild Docker Image

## ⚠️ Diagnostic du Problème

Vous avez actuellement **deux problèmes** :

### 1. Service Unavailable (503)
```bash
docker exec qbittorrent wget -O- http://grab2rss:8000/health
# wget: server returned error: HTTP/1.1 503 Service Unavailable
```

**Cause** : L'application démarre encore. Status actuel : `(health: starting)`

**Solution** : Attendre 30 secondes puis retester.

### 2. URL Incorrecte Persistante
```json
"http://localhost:8000/torrents/data%2Ftorrents%2FThrough%20My%20Window.torrent"
```

**Cause** : L'**ancienne image Docker** est utilisée avec l'ancien code (celui qui retourne le chemin complet).

**Solution** : Reconstruire l'image Docker avec le nouveau code.

---

## ✅ Solution : Rebuild Complet

### Étape 1 : Arrêter le Conteneur

```bash
cd ~/projets/grabb2rss
docker compose down
```

### Étape 2 : Supprimer l'Ancienne Image

```bash
docker rmi grabb2rss-grab2rss

# Ou forcer si besoin
docker rmi -f grabb2rss-grab2rss
```

### Étape 3 : Vérifier les Fichiers Locaux

**CRITIQUE** : Assurez-vous d'avoir les **nouveaux fichiers** dans votre dossier `~/projets/grabb2rss` :

```bash
# Vérifier torrent.py
grep "return filename" torrent.py

# Devrait afficher 2 lignes :
#     return filename
#     return filename

# Si ça affiche "return str(path)", vous avez l'ANCIEN fichier !
```

**Si vous avez les anciens fichiers** :
1. Téléchargez les nouveaux fichiers que je vous ai fournis
2. Remplacez `torrent.py` et `radarr_sonarr.py` dans `~/projets/grabb2rss`

### Étape 4 : Rebuild SANS Cache

```bash
# Rebuild complet sans cache
docker compose build --no-cache

# Cela va :
# - Recréer l'image from scratch
# - Utiliser le NOUVEAU code
# - Installer toutes les dépendances
```

### Étape 5 : Démarrer

```bash
docker compose up -d
```

### Étape 6 : Attendre le Démarrage

```bash
# Attendre 15 secondes
sleep 15

# Vérifier le status
docker ps | grep grab2rss

# Devrait afficher : (healthy) au lieu de (health: starting)
```

### Étape 7 : Tester

```bash
# Test 1 : Health
curl http://localhost:8000/health

# Devrait afficher :
# {"status":"ok","components":{"database":"ok","prowlarr":"ok","scheduler":"ok"}}

# Test 2 : URL RSS (LE PLUS IMPORTANT)
curl http://localhost:8000/rss/torrent.json | jq '.items[0].link'

# ✅ DOIT afficher :
# "http://localhost:8000/torrents/Through%20My%20Window.torrent"

# ❌ NE DOIT PAS afficher :
# "http://localhost:8000/torrents/data%2Ftorrents%2F..."
```

---

## 🧪 Validation Complète

```bash
# 1. Vérifier que grab2rss est healthy
docker ps | grep grab2rss
# Cherchez : (healthy) dans la sortie

# 2. Vérifier les logs
docker compose logs -f grab2rss
# Devrait afficher : ✅ Application démarrée v2.5

# 3. Tester le health endpoint
curl http://localhost:8000/health | jq

# 4. Tester l'URL RSS
curl http://localhost:8000/rss/torrent.json | jq '.items[0]'

# 5. Tester depuis qBittorrent
docker exec qbittorrent wget -O- http://grab2rss:8000/health
```

---

## 📋 Checklist de Vérification

Avant de rebuild, vérifiez :

- [ ] Je suis dans le bon dossier : `cd ~/projets/grabb2rss`
- [ ] J'ai les **nouveaux fichiers** torrent.py et radarr_sonarr.py
- [ ] J'ai vérifié que `torrent.py` contient `return filename` (ligne 41 et 66)
- [ ] J'ai arrêté le conteneur : `docker compose down`
- [ ] J'ai supprimé l'ancienne image : `docker rmi grabb2rss-grab2rss`
- [ ] Je rebuild SANS cache : `docker compose build --no-cache`
- [ ] Je redémarre : `docker compose up -d`
- [ ] J'attends 15 secondes : `sleep 15`
- [ ] Je teste l'URL : Elle NE contient PAS `data%2Ftorrents`

---

## 🔍 Vérifier Quel Fichier est Utilisé

Pour être **100% sûr** que Docker utilise le nouveau code :

```bash
# Entrer dans le conteneur en cours d'exécution
docker exec -it grab2rss /bin/bash

# Vérifier le contenu de torrent.py
grep -n "return filename\|return str(path)" /app/torrent.py

# Devrait afficher :
#     41:        return filename
#     66:        return filename

# Si ça affiche "return str(path)", c'est l'ancien code !
# Il faut rebuild

# Sortir du conteneur
exit
```

---

## ⚡ Commandes Rapides (Tout en Une)

```bash
cd ~/projets/grabb2rss

# 1. Tout arrêter et nettoyer
docker compose down
docker rmi -f grabb2rss-grab2rss
docker system prune -f

# 2. S'assurer d'avoir les nouveaux fichiers
# IMPORTANT : Remplacez torrent.py et radarr_sonarr.py si besoin !

# 3. Rebuild from scratch
docker compose build --no-cache

# 4. Démarrer
docker compose up -d

# 5. Attendre
sleep 15

# 6. Tester
echo "=== TEST HEALTH ==="
curl http://localhost:8000/health | jq

echo ""
echo "=== TEST URL RSS ==="
curl http://localhost:8000/rss/torrent.json | jq '.items[0].link'

echo ""
echo "=== TEST DEPUIS QBITTORRENT ==="
docker exec qbittorrent wget -O- http://grab2rss:8000/health
```

---

## ✅ Résultat Attendu

### Health Check
```json
{
  "status": "ok",
  "timestamp": "2026-01-19T...",
  "version": "2.5.0",
  "components": {
    "database": "ok",
    "prowlarr": "ok",
    "scheduler": "ok"
  }
}
```

### URL RSS
```json
{
  "id": "grab-1",
  "title": "Through My Window 2022...",
  "link": "http://localhost:8000/torrents/Through%20My%20Window%202022%20MULTi%201080p%20WEB%20x264-STRINGERBELL.torrent",
  "torrent": "http://localhost:8000/torrents/Through%20My%20Window%202022%20MULTi%201080p%20WEB%20x264-STRINGERBELL.torrent"
}
```

**✅ Pas de `data%2Ftorrents` dans l'URL !**

### Test qBittorrent
```json
{"status":"ok",...}
```

**✅ Pas d'erreur 503 !**

---

## 🆘 Si ça ne Fonctionne Toujours Pas

### Vérifier les Fichiers Sources

```bash
cd ~/projets/grabb2rss

# Afficher les lignes critiques de torrent.py
sed -n '40,42p; 65,67p' torrent.py

# DOIT afficher :
#     if path.exists():
#         return filename  # ← CRUCIAL
#     
#     ...
#     
#         # Retourner SEULEMENT le nom du fichier (pas le chemin complet)
#         return filename  # ← CRUCIAL
```

### Si vous voyez `return str(path)`, c'est l'ANCIEN FICHIER

Remplacez `torrent.py` par le nouveau fichier fourni dans les téléchargements ci-dessus.

### Logs en Direct

```bash
# Voir les logs pendant le démarrage
docker compose logs -f grab2rss

# Cherchez :
# ✅ Configuration chargée depuis...
# ✅ Configuration valide
# ✅ Application démarrée v2.5

# Si vous voyez des erreurs, notez-les
```

---

## 💡 Pourquoi ça Arrive ?

Docker **met en cache** les layers de build. Même si vous modifiez le code, Docker peut utiliser l'ancienne version cachée.

**Solution** : `docker compose build --no-cache` force un rebuild complet sans utiliser le cache.

---

**Suivez ces étapes dans l'ordre et ça fonctionnera !** 🚀
