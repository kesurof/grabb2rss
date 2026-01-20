# 🚀 Migration v2.5 - Filtrage Radarr/Sonarr

## ✨ Nouvelle Fonctionnalité

Grab2RSS v2.5 **vérifie maintenant** si les grabs Prowlarr ont été **réellement importés** dans Radarr/Sonarr avant de les ajouter au flux RSS.

**Résultat** : Fini les faux positifs ! Seulement les fichiers **vraiment téléchargés et importés**.

---

## 📊 Avant vs Après

### ❌ Avant (v2.4)

```
Prowlarr : 150 grabs Radarr + 23 grabs Sonarr
Grab2RSS : 173 torrents dans le flux RSS
Problème : Beaucoup de torrents rejetés par Radarr/Sonarr
```

### ✅ Après (v2.5)

```
Prowlarr : 150 grabs Radarr + 23 grabs Sonarr
Radarr downloadFolderImported : 3 fichiers (Hitman, Predator, Rental)
Sonarr downloadFolderImported : 2 fichiers (Tehran S03E01, S03E02)
Grab2RSS : 5 torrents dans le flux RSS
```

---

## 🔧 Installation

### 1️⃣ Fichiers à Remplacer (5)

- `radarr_sonarr.py` (NOUVEAU)
- `config.py`
- `scheduler.py`
- `prowlarr.py`
- `db.py`

### 2️⃣ Configuration

Éditez votre `.env` et ajoutez :

```env
# Radarr (Optionnel mais recommandé)
RADARR_URL=http://localhost:7878
RADARR_API_KEY=2b7f0f74e5

# Sonarr (Optionnel mais recommandé)
SONARR_URL=http://localhost:8989
SONARR_API_KEY=9c90802810a2

# Prowlarr (augmenter pour récupérer plus)
PROWLARR_HISTORY_PAGE_SIZE=500
```

### 3️⃣ Supprimer la Config DB

```bash
cd ~/scripts/grabb2rss
sqlite3 data/grabs.db "DELETE FROM config;"
```

### 4️⃣ Purger les Anciens Grabs

```bash
curl -X POST http://localhost:8000/api/purge/all
```

### 5️⃣ Redémarrer

```bash
python main.py
```

---

## 🎯 Comment Ça Fonctionne

### Flux de Vérification

```
1. Prowlarr API → Récupère tous les grabs (grabbed)
2. Radarr API → Récupère downloadFolderImported (vrais imports)
3. Sonarr API → Récupère downloadFolderImported (vrais imports)
4. Comparaison → Ne garde que les titres importés
5. Grab2RSS → Ajoute UNIQUEMENT les vrais torrents
```

### Cache Intelligent

- Les titres importés sont **mis en cache 5 minutes**
- Évite de surcharger Radarr/Sonarr à chaque sync
- Force refresh automatique après 5min

---

## 📝 Logs de Sync

**Avec vérification activée** :

```
⏱️  Sync Prowlarr en cours...
📥 Radarr: 23 titres importés récupérés
📺 Sonarr: 45 titres importés récupérés
✅ Total: 68 titres importés dans le cache
🔍 Vérification activée: 68 titres importés

✔️  Hitman's Wife's Bodyguard 2021 MULTi VFQ 1080p BluRay AC3 x265-Winks
✔️  Predator Badlands 2025 MULTi VF2 1080p WEB H264-SUPPLY
✔️  Rental Family 2025 MULTi VFQ 1080p WEB H264-SUPPLY
✔️  Tehran S03E02 MULTI 1080p WEB H264-HiggsBoson (Téhéran)
✔️  Tehran S03E01 MULTI 1080p WEB H264-HiggsBoson (Téhéran)

⊘ Non importé: Edward Scissorhands (1990) (Remastered) Multi VFF 1080p BluRay mHD x264 DTS-PuNiSHeR03
⊘ Non importé: Dune 1984 FRENCH 720p BluRay DTS x264-PURE
⊘ Non importé: Atomic Blonde 2017 Truefrench 720p BluRay x264 AAC-PiXEL

✅ Sync terminée: 5 grabs, 0 doublons, 145 non importés
```

**Sans vérification (APIs non configurées)** :

```
⏱️  Sync Prowlarr en cours...
ℹ️  Vérification Radarr/Sonarr désactivée (pas de config)

✔️  [Tous les grabs Prowlarr, même non importés]

✅ Sync terminée: 150 grabs, 0 doublons
```

---

## ⚙️ Configuration Avancée

### Désactiver la Vérification

Laissez les champs vides dans `.env` :

```env
RADARR_URL=
RADARR_API_KEY=
SONARR_URL=
SONARR_API_KEY=
```

### Vérifier Seulement Radarr

```env
RADARR_URL=http://localhost:7878
RADARR_API_KEY=your_key
SONARR_URL=
SONARR_API_KEY=
```

### Augmenter l'Historique Vérifié

Par défaut, Grab2RSS vérifie les **200 derniers imports**. Pour augmenter, modifiez `radarr_sonarr.py` :

```python
# Ligne 25 et 50
page_size: int = 500  # Au lieu de 200
```

---

## 🧪 Tests

### Test 1 : Vérifier que ça fonctionne

```bash
# Avant purge
curl -s http://localhost:8000/api/stats | jq '.total_grabs'
# Devrait afficher : 150+

# Après purge et resync
curl -X POST http://localhost:8000/api/purge/all
curl -X POST http://localhost:8000/api/sync/trigger
sleep 30
curl -s http://localhost:8000/api/stats | jq '.total_grabs'
# Devrait afficher : 5-10 (seulement les vrais imports)
```

### Test 2 : Vérifier les titres récupérés

```bash
curl -s http://localhost:8000/api/grabs | jq '.[] | .title'
```

Vous devriez voir **SEULEMENT** :
- Hitman's Wife's Bodyguard
- Predator Badlands
- Rental Family
- Tehran S03E01
- Tehran S03E02

---

## 🐛 Dépannage

### Problème : Trop de grabs rejetés

**Solution** : Augmenter `page_size` dans `radarr_sonarr.py` (ligne 25 et 50) :

```python
page_size: int = 500
```

### Problème : Erreur API Radarr/Sonarr

```
⚠️  Erreur Radarr API: Connection refused
```

**Solution** : Vérifier les URLs dans `.env` :

```bash
# Test manuel
curl http://localhost:7878/api/v3/system/status -H "X-Api-Key: YOUR_KEY"
curl http://localhost:8989/api/v3/system/status -H "X-Api-Key: YOUR_KEY"
```

### Problème : Cache trop court/long

Modifier `CACHE_DURATION` dans `radarr_sonarr.py` (ligne 12) :

```python
CACHE_DURATION = 600  # 10 minutes au lieu de 5
```

---

## 📈 Performance

### Impact

- **+2-3 secondes** par sync (appels API Radarr/Sonarr)
- **Cache** : Pas d'impact après le premier appel (5 minutes)
- **Résultat** : Flux RSS 30x plus petit et pertinent !

### Optimisations

- Cache de 5 minutes pour éviter trop d'appels API
- Normalisation des titres pour comparaison rapide
- Appels parallèles Radarr + Sonarr (non bloquants)

---

## 🎉 Résultat Final

**Flux RSS** : Seulement les 5 vrais téléchargements  
**qBittorrent** : Télécharge seulement les bons torrents  
**Seeding** : Efficace et pertinent

**Fini les faux positifs ! 🚀**
