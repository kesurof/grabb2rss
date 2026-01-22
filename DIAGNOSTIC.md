# 🔍 Script de Diagnostic Grabb2RSS

Ce script analyse en profondeur votre installation Grabb2RSS et génère un rapport détaillé.

## 📋 Qu'est-ce qui est vérifié ?

Le script analyse **6 catégories** :

### 1. 📁 Système de fichiers
- Présence des fichiers critiques (`settings.yml`, `main.py`, etc.)
- Permissions sur les fichiers et répertoires
- Espace disque disponible
- UID/GID et droits d'accès

### 2. ⚙️ Configuration
- Validité du fichier `settings.yml`
- Présence de toutes les sections requises
- État du setup (complété ou non)
- Configuration de Prowlarr, Radarr, Sonarr
- Paramètres de synchronisation et RSS

### 3. 💾 Base de données
- Présence et taille de la base SQLite
- Liste des tables et nombre d'entrées
- Statistiques sur les grabs
- Historique des synchronisations
- Analyse des trackers

### 4. 🔗 Services externes
- Connectivité à Prowlarr
- Connectivité à Radarr (si activé)
- Connectivité à Sonarr (si activé)
- Temps de réponse de chaque service

### 5. 🌐 Endpoints API
- Test de tous les endpoints principaux (`/health`, `/api/stats`, etc.)
- Codes HTTP retournés
- Temps de réponse
- Détection des endpoints inaccessibles

### 6. 🐍 Environnement
- Version Python et plateforme
- Variables d'environnement (`PUID`, `PGID`, `TZ`, etc.)
- Modules Python requis
- Répertoire de travail

## 🚀 Utilisation

### Dans Docker (recommandé)

```bash
# Lancer le diagnostic
docker exec grabb2rss python /app/diagnose.py

# Ou si votre conteneur a un autre nom
docker exec <nom_conteneur> python /app/diagnose.py
```

### En local

```bash
cd /chemin/vers/grabb2rss
python diagnose.py
```

## 📊 Sorties du script

### 1. Sortie console (stdout)
Un rapport détaillé et formaté s'affiche dans le terminal avec :
- ✅ Éléments OK
- ⚠️ Avertissements
- ❌ Erreurs
- 🔴 Problèmes critiques

### 2. Rapport JSON
Un fichier JSON complet est généré : `/config/diagnostic_report.json`

Structure :
```json
{
  "timestamp": "2026-01-22T18:30:00.000000",
  "version": "1.0.0",
  "status": "healthy|warning|degraded|critical",
  "sections": {
    "filesystem": { ... },
    "configuration": { ... },
    "database": { ... },
    "services": { ... },
    "api": { ... },
    "environment": { ... }
  },
  "issues": [ ... ],
  "warnings": [ ... ],
  "summary": {
    "total_issues": 0,
    "total_warnings": 2,
    "critical_issues": 0,
    "errors": 0
  }
}
```

## 🔍 Interprétation des résultats

### Statut global

| Statut | Icône | Signification |
|--------|-------|---------------|
| `healthy` | ✅ | Tout fonctionne parfaitement |
| `warning` | ⚠️ | Avertissements mineurs (ex: setup non complété) |
| `degraded` | ❌ | Problèmes affectant des fonctionnalités |
| `critical` | 🔴 | Problèmes bloquants (fichiers manquants, etc.) |

### Codes de sortie

- `0` : Tout est OK (healthy)
- `1` : Avertissements ou dégradé (warning/degraded)
- `2` : Critique (critical)

## 📝 Exemple d'utilisation pour debugging

```bash
# 1. Lancer le diagnostic et sauvegarder la sortie
docker exec grabb2rss python /app/diagnose.py > diagnostic_output.txt 2>&1

# 2. Récupérer le rapport JSON
docker cp grabb2rss:/config/diagnostic_report.json .

# 3. Consulter le rapport
cat diagnostic_output.txt
cat diagnostic_report.json | jq '.'
```

## 🐛 Cas d'usage typiques

### Problème : Pages retournent 404
```bash
docker exec grabb2rss python /app/diagnose.py
# Vérifier section "configuration" et "api"
```

### Problème : Synchronisation ne fonctionne pas
```bash
docker exec grabb2rss python /app/diagnose.py
# Vérifier section "services" (Prowlarr)
# Vérifier section "database" (sync_logs)
```

### Problème : Permissions
```bash
docker exec grabb2rss python /app/diagnose.py
# Vérifier section "filesystem" (permissions, UID/GID)
```

### Première installation
```bash
docker exec grabb2rss python /app/diagnose.py
# Devrait montrer "warning" car setup non complété
# Normal, configurez via http://localhost:8000/setup
```

## 🔧 Que faire après le diagnostic ?

1. **Consultez le résumé** en fin de rapport
2. **Identifiez les problèmes critiques** (🔴) en priorité
3. **Corrigez les erreurs** (❌) ensuite
4. **Examinez les avertissements** (⚠️) si nécessaire
5. **Partagez le rapport** avec le support si besoin

## 💡 Conseils

- Lancez le diagnostic **après chaque changement de configuration**
- Sauvegardez le rapport JSON pour comparaison ultérieure
- En cas de problème, incluez TOUJOURS la sortie du diagnostic dans vos rapports de bug

## 📬 Support

Si le diagnostic révèle des problèmes que vous ne pouvez pas résoudre :

1. Récupérez la sortie complète du script
2. Récupérez le fichier `/config/diagnostic_report.json`
3. Ouvrez une issue sur GitHub avec ces informations
