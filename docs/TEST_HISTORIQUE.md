# 🔍 GUIDE DE TEST - LIMITES D'HISTORIQUE

## Objectif
Déterminer jusqu'où on peut remonter dans l'historique de Prowlarr, Radarr et Sonarr.

---

## 📋 PRÉREQUIS

Avant de tester, récupérez vos informations de configuration :

```bash
# Voir votre configuration actuelle
cat /config/settings.yml
# OU
cat .env
```

Vous aurez besoin de :
- `PROWLARR_URL` et `PROWLARR_API_KEY`
- `RADARR_URL` et `RADARR_API_KEY` (si activé)
- `SONARR_URL` et `SONARR_API_KEY` (si activé)

---

## 🎯 TESTS PROWLARR

### Test 1 : Historique avec pageSize par défaut (100)

```bash
curl -X GET "http://VOTRE_PROWLARR_URL/api/v1/history?pageSize=100" \
  -H "X-Api-Key: VOTRE_PROWLARR_API_KEY" \
  | jq '[.records[] | {date: .date, title: .sourceTitle, eventType: .eventType}] | .[0], .[-1]'
```

**Ce que ça montre :** Le premier et dernier enregistrement (dates extrêmes)

---

### Test 2 : Augmenter le pageSize à 500

```bash
curl -X GET "http://VOTRE_PROWLARR_URL/api/v1/history?pageSize=500" \
  -H "X-Api-Key: VOTRE_PROWLARR_API_KEY" \
  | jq '[.records[] | {date: .date, title: .sourceTitle, eventType: .eventType}] | .[0], .[-1]'
```

**Ce que ça montre :** Si augmenter le pageSize permet de remonter plus loin

---

### Test 3 : Tester le maximum absolu (1000)

```bash
curl -X GET "http://VOTRE_PROWLARR_URL/api/v1/history?pageSize=1000" \
  -H "X-Api-Key: VOTRE_PROWLARR_API_KEY" \
  | jq '[.records[] | {date: .date, title: .sourceTitle, eventType: .eventType}] | .[0], .[-1]'
```

**Ce que ça montre :** La limite maximale acceptée par l'API

---

### Test 4 : Compter les enregistrements disponibles

```bash
curl -X GET "http://VOTRE_PROWLARR_URL/api/v1/history?pageSize=1000" \
  -H "X-Api-Key: VOTRE_PROWLARR_API_KEY" \
  | jq '.records | length'
```

**Ce que ça montre :** Le nombre exact d'enregistrements retournés

---

### Test 5 : Analyser les dates des grabs réussis

```bash
curl -X GET "http://VOTRE_PROWLARR_URL/api/v1/history?pageSize=500" \
  -H "X-Api-Key: VOTRE_PROWLARR_API_KEY" \
  | jq '[.records[] | select(.eventType == "releaseGrabbed" and .successful == true) | {date: .date, title: .sourceTitle}] | .[0], .[-1]'
```

**Ce que ça montre :** Premier et dernier grab RÉUSSI (ce qui est utilisé par grabb2rss)

---

### Test 6 : Pagination (si supportée)

```bash
# Page 1
curl -X GET "http://VOTRE_PROWLARR_URL/api/v1/history?page=1&pageSize=100" \
  -H "X-Api-Key: VOTRE_PROWLARR_API_KEY" \
  | jq '.page, .totalRecords, .records | length'

# Page 2
curl -X GET "http://VOTRE_PROWLARR_URL/api/v1/history?page=2&pageSize=100" \
  -H "X-Api-Key: VOTRE_PROWLARR_API_KEY" \
  | jq '.page, .totalRecords, .records | length'
```

**Ce que ça montre :** Si la pagination permet d'accéder à plus d'historique

---

## 🎬 TESTS RADARR

### Test 1 : Historique Radarr (pageSize 200)

```bash
curl -X GET "http://VOTRE_RADARR_URL/api/v3/history?pageSize=200" \
  -H "X-Api-Key: VOTRE_RADARR_API_KEY" \
  | jq '[.records[] | {date: .date, title: .sourceTitle, eventType: .eventType}] | .[0], .[-1]'
```

---

### Test 2 : Filtrer uniquement les grabs

```bash
curl -X GET "http://VOTRE_RADARR_URL/api/v3/history?pageSize=200" \
  -H "X-Api-Key: VOTRE_RADARR_API_KEY" \
  | jq '[.records[] | select(.eventType == "grabbed") | {date: .date, title: .sourceTitle, downloadId: .downloadId}] | .[0], .[-1]'
```

---

### Test 3 : Compter les grabs disponibles

```bash
curl -X GET "http://VOTRE_RADARR_URL/api/v3/history?pageSize=500" \
  -H "X-Api-Key: VOTRE_RADARR_API_KEY" \
  | jq '[.records[] | select(.eventType == "grabbed")] | length'
```

---

## 📺 TESTS SONARR

### Test 1 : Historique Sonarr (pageSize 200)

```bash
curl -X GET "http://VOTRE_SONARR_URL/api/v3/history?pageSize=200" \
  -H "X-Api-Key: VOTRE_SONARR_API_KEY" \
  | jq '[.records[] | {date: .date, title: .sourceTitle, eventType: .eventType}] | .[0], .[-1]'
```

---

### Test 2 : Filtrer uniquement les grabs

```bash
curl -X GET "http://VOTRE_SONARR_URL/api/v3/history?pageSize=200" \
  -H "X-Api-Key: VOTRE_SONARR_API_KEY" \
  | jq '[.records[] | select(.eventType == "grabbed") | {date: .date, title: .sourceTitle, downloadId: .downloadId}] | .[0], .[-1]'
```

---

### Test 3 : Compter les grabs disponibles

```bash
curl -X GET "http://VOTRE_SONARR_URL/api/v3/history?pageSize=500" \
  -H "X-Api-Key: VOTRE_SONARR_API_KEY" \
  | jq '[.records[] | select(.eventType == "grabbed")] | length'
```

---

## 🔄 TEST DE CORRÉLATION PROWLARR ↔ RADARR/SONARR

### Vérifier si un grab Prowlarr existe dans Radarr/Sonarr

```bash
# 1. Récupérer un downloadId depuis Prowlarr
DOWNLOAD_ID=$(curl -s -X GET "http://VOTRE_PROWLARR_URL/api/v1/history?pageSize=10" \
  -H "X-Api-Key: VOTRE_PROWLARR_API_KEY" \
  | jq -r '.records[] | select(.eventType == "releaseGrabbed" and .successful == true) | .downloadId' \
  | head -1)

echo "Testing downloadId: $DOWNLOAD_ID"

# 2. Chercher ce downloadId dans Radarr
curl -s -X GET "http://VOTRE_RADARR_URL/api/v3/history?pageSize=500" \
  -H "X-Api-Key: VOTRE_RADARR_API_KEY" \
  | jq --arg id "$DOWNLOAD_ID" '.records[] | select(.downloadId == $id)'

# 3. Chercher ce downloadId dans Sonarr
curl -s -X GET "http://VOTRE_SONARR_URL/api/v3/history?pageSize=500" \
  -H "X-Api-Key: VOTRE_SONARR_API_KEY" \
  | jq --arg id "$DOWNLOAD_ID" '.records[] | select(.downloadId == $id)'
```

---

## 📊 INTERPRÉTATION DES RÉSULTATS

### Cas 1 : Limitation par nombre d'enregistrements
Si l'augmentation du `pageSize` permet de remonter plus loin :
- ✅ La limite est le `pageSize`
- ✅ Solution : Augmenter `PROWLARR_HISTORY_PAGE_SIZE` dans la config

### Cas 2 : Limitation temporelle de l'API
Si même avec `pageSize=1000`, vous ne remontez que jusqu'à hier 9h30 :
- ⚠️ C'est une limite de l'API Prowlarr elle-même
- ⚠️ Prowlarr purge peut-être automatiquement son historique
- ⚠️ Vérifier les paramètres de rétention dans Prowlarr

### Cas 3 : Pagination fonctionnelle
Si `page=2` retourne des enregistrements différents de `page=1` :
- 💡 On peut implémenter la pagination pour récupérer tout l'historique
- 💡 Nécessite une modification du code pour gérer plusieurs pages

---

## ⚙️ VÉRIFIER LES PARAMÈTRES PROWLARR

Connectez-vous à Prowlarr et vérifiez :

1. **Settings → General → History Cleanup**
   - Combien de jours d'historique sont conservés ?

2. **Settings → Database**
   - Taille de la base de données
   - Nombre d'enregistrements

---

## 🛠️ SCRIPT DE TEST COMPLET

Voici un script qui teste tout automatiquement :

```bash
#!/bin/bash

# === CONFIGURATION ===
# Remplacez par vos valeurs
PROWLARR_URL="http://localhost:9696"
PROWLARR_API_KEY="votre_cle_api"
RADARR_URL="http://localhost:7878"
RADARR_API_KEY="votre_cle_api"
SONARR_URL="http://localhost:8989"
SONARR_API_KEY="votre_cle_api"

echo "=== TEST LIMITES HISTORIQUE ==="
echo ""

# Test Prowlarr
echo "📡 PROWLARR"
for size in 50 100 200 500 1000; do
  count=$(curl -s -X GET "${PROWLARR_URL}/api/v1/history?pageSize=${size}" \
    -H "X-Api-Key: ${PROWLARR_API_KEY}" \
    | jq '.records | length')

  oldest=$(curl -s -X GET "${PROWLARR_URL}/api/v1/history?pageSize=${size}" \
    -H "X-Api-Key: ${PROWLARR_API_KEY}" \
    | jq -r '.records[-1].date')

  echo "  pageSize=$size → $count enregistrements, plus ancien: $oldest"
done

echo ""
echo "🎬 RADARR"
count=$(curl -s -X GET "${RADARR_URL}/api/v3/history?pageSize=500" \
  -H "X-Api-Key: ${RADARR_API_KEY}" \
  | jq '[.records[] | select(.eventType == "grabbed")] | length')

oldest=$(curl -s -X GET "${RADARR_URL}/api/v3/history?pageSize=500" \
  -H "X-Api-Key: ${RADARR_API_KEY}" \
  | jq -r '[.records[] | select(.eventType == "grabbed")] | .[-1].date')

echo "  $count grabs, plus ancien: $oldest"

echo ""
echo "📺 SONARR"
count=$(curl -s -X GET "${SONARR_URL}/api/v3/history?pageSize=500" \
  -H "X-Api-Key: ${SONARR_API_KEY}" \
  | jq '[.records[] | select(.eventType == "grabbed")] | length')

oldest=$(curl -s -X GET "${SONARR_URL}/api/v3/history?pageSize=500" \
  -H "X-Api-Key: ${SONARR_API_KEY}" \
  | jq -r '[.records[] | select(.eventType == "grabbed")] | .[-1].date')

echo "  $count grabs, plus ancien: $oldest"
```

---

## 💡 ACTIONS RECOMMANDÉES SELON LES RÉSULTATS

### Si limitation par pageSize
```yaml
# /config/settings.yml
prowlarr:
  history_page_size: 500  # Augmenter
```

### Si limitation temporelle API
- Modifier le code pour gérer la pagination
- Configurer la rétention dans Prowlarr
- Accepter la limitation

### Si décalage Prowlarr ↔ Radarr/Sonarr
- Augmenter aussi le pageSize de Radarr/Sonarr (actuellement 200)
- Modifier `radarr_sonarr.py` ligne 20 et 69

---

## 📝 NOTES

- `jq` est requis pour parser le JSON : `apt-get install jq`
- Les URLs doivent être sans `/` à la fin
- Les dates sont en ISO 8601 UTC
- `pageSize` maximum varie selon les APIs (généralement 1000)
