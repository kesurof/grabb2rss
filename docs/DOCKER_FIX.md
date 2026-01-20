# 🐳 Guide de Résolution des Problèmes Docker

## ✅ Problème 1 : Build Docker Échoue (psutil)

### Erreur
```
ERROR: Failed building wheel for psutil
ERROR: Could not build wheels for psutil
```

### ✅ Solution : Dockerfile Corrigé

Le nouveau `Dockerfile` inclut maintenant les dépendances nécessaires :

```dockerfile
# Installer gcc et python3-dev pour compiler psutil
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    curl \
    gcc \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*
```

**Action** : Utilisez le nouveau `Dockerfile` fourni.

---

## ✅ Problème 2 : docker-compose Ne Fonctionne Pas

### Erreur
```
ModuleNotFoundError: No module named 'compose'
```

### Cause
Votre environnement virtuel Python (venv) contient une vieille version cassée de `docker-compose`.

### ✅ Solution A : Utiliser `docker compose` (RECOMMANDÉ)

Docker moderne (v20.10+) intègre `compose` directement.

**Depuis VSCode** :
```bash
# Remplacer docker-compose par docker compose
docker compose -f docker-compose.yml up -d --build
```

**Depuis le terminal** :
```bash
# SORTIR du venv d'abord !
deactivate

# Puis utiliser docker compose (sans tiret)
docker compose up -d --build
```

### ✅ Solution B : Désactiver le venv

Le problème vient du venv Python qui override `docker-compose`.

```bash
# 1. Sortir du venv
deactivate

# 2. Vérifier que docker-compose fonctionne
docker-compose --version

# 3. Builder
docker-compose up -d --build
```

### ✅ Solution C : Installer docker-compose Système

Si `docker compose` n'existe pas :

```bash
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install docker-compose-plugin

# Vérifier
docker compose version
```

---

## 🚀 Commandes Correctes

### Build et Démarrage

```bash
# MÉTHODE 1 : Docker Compose moderne (sans venv)
deactivate  # Sortir du venv
docker compose up -d --build

# MÉTHODE 2 : Docker Compose classique (sans venv)
deactivate
docker-compose up -d --build

# MÉTHODE 3 : Depuis VSCode (modifier la commande)
# Remplacer dans tasks.json ou dans le terminal :
docker compose -f docker-compose.yml up -d --build
```

### Vérification

```bash
# Voir les logs
docker compose logs -f grab2rss
# OU
docker-compose logs -f grab2rss

# Vérifier le statut
docker compose ps
# OU
docker-compose ps

# Healthcheck
curl http://localhost:8000/health
```

---

## 📋 Checklist de Dépannage

### Avant de Builder

- [ ] Sortir du venv Python : `deactivate`
- [ ] Vérifier Docker : `docker --version`
- [ ] Vérifier Compose : `docker compose version` OU `docker-compose --version`
- [ ] Être dans le bon dossier : `ls -la` (doit montrer Dockerfile)

### Build

```bash
# 1. Nettoyer les anciennes images (optionnel)
docker compose down
docker system prune -f

# 2. Builder avec le nouveau Dockerfile
docker compose up -d --build

# 3. Vérifier les logs
docker compose logs -f
```

### Si ça ne Build Pas

```bash
# 1. Arrêter tout
docker compose down

# 2. Supprimer l'image
docker rmi grab2rss_grab2rss

# 3. Rebuild from scratch
docker compose build --no-cache
docker compose up -d

# 4. Vérifier
docker compose ps
```

---

## 🔧 Configuration VSCode (Optionnel)

Si vous utilisez VSCode, mettez à jour votre `tasks.json` :

```json
{
    "version": "2.0.0",
    "tasks": [
        {
            "label": "Docker Compose Up",
            "type": "shell",
            "command": "docker compose -f docker-compose.yml up -d --build",
            "problemMatcher": []
        },
        {
            "label": "Docker Compose Down",
            "type": "shell",
            "command": "docker compose -f docker-compose.yml down",
            "problemMatcher": []
        },
        {
            "label": "Docker Compose Logs",
            "type": "shell",
            "command": "docker compose -f docker-compose.yml logs -f",
            "problemMatcher": []
        }
    ]
}
```

**Remarque** : Notez `docker compose` (SANS tiret) au lieu de `docker-compose`.

---

## ✅ Installation Manuelle (Alternative)

Si Docker pose problème, vous pouvez lancer manuellement :

```bash
# 1. Sortir du venv (si dedans)
deactivate

# 2. Créer un nouveau venv propre
python3 -m venv venv

# 3. Activer
source venv/bin/activate

# 4. Installer les dépendances
pip install --upgrade pip
pip install -r requirements.txt

# 5. Configuration
cp .env.example .env
nano .env  # PROWLARR_API_KEY

# 6. Lancer
python main.py
```

---

## 🎯 Résumé des Corrections

### Dockerfile
- ✅ Ajout de `gcc` pour compiler psutil
- ✅ Ajout de `python3-dev` pour les headers Python
- ✅ Upgrade de pip avant installation

### docker-compose
- ✅ Utiliser `docker compose` (moderne, sans tiret)
- ✅ OU sortir du venv avant d'utiliser `docker-compose`

---

## 💡 Pourquoi Ces Erreurs ?

### psutil
`psutil` est un module Python écrit en C. Il nécessite :
- Un compilateur C (`gcc`)
- Les headers Python (`python3-dev`)
- Sans eux, pip ne peut pas compiler les binaires

### docker-compose
Votre venv contient une version cassée de `docker-compose` installée via pip. Solutions :
1. Utiliser `docker compose` (intégré à Docker)
2. Sortir du venv
3. Réinstaller docker-compose correctement

---

## 🚀 Commande Unique pour Tout Réparer

```bash
# 1. Tout nettoyer
deactivate
docker compose down 2>/dev/null || docker-compose down 2>/dev/null
docker system prune -f

# 2. Rebuild from scratch
docker compose build --no-cache
docker compose up -d

# 3. Vérifier
docker compose ps
docker compose logs -f grab2rss

# 4. Tester
curl http://localhost:8000/health
```

---

## 📞 Encore des Problèmes ?

### Vérifier votre version Docker

```bash
docker --version
# Doit afficher >= 20.10

docker compose version
# OU
docker-compose --version
```

### Vérifier les permissions

```bash
# Votre user doit être dans le groupe docker
groups
# Doit contenir 'docker'

# Sinon, ajouter :
sudo usermod -aG docker $USER
# Puis se déconnecter/reconnecter
```

### Logs détaillés

```bash
# Build avec verbose
docker compose build --progress=plain --no-cache

# Logs de l'app
docker compose logs -f --tail=100 grab2rss
```

---

**Version corrigée prête à l'emploi !** 🎉
