# 🌐 Configuration Réseau traefik_proxy

## ✅ docker-compose.yml Corrigé

Le fichier utilise maintenant le réseau Docker **existant** `traefik_proxy` :

```yaml
networks:
  traefik_proxy:
    external: true  # Utilise un réseau existant
```

**IMPORTANT** : Le réseau s'appelle `traefik_proxy` (avec underscore `_`), pas `traefik-proxy` (avec tiret `-`).

---

## 🚀 Démarrage

```bash
# 1. Vérifier que le réseau existe
docker network ls | grep traefik_proxy

# 2. Démarrer Grab2RSS
docker compose up -d --build

# 3. Vérifier que grab2rss est bien sur le réseau
docker network inspect traefik_proxy | grep grab2rss
```

---

## 🔧 Connecter qBittorrent au Réseau

Si qBittorrent n'est pas déjà sur `traefik_proxy` :

```bash
# Connecter le conteneur qbittorrent
docker network connect traefik_proxy qbittorrent

# Vérifier
docker network inspect traefik_proxy | grep qbittorrent
```

---

## 🎯 Configuration qBittorrent

Dans qBittorrent, utiliser l'URL :

```
http://grab2rss:8000/rss/torrent.json
```

**Note** : `grab2rss` est le nom du conteneur défini dans `container_name: grab2rss`

---

## 🧪 Tests de Connectivité

```bash
# Test 1 : Ping depuis qBittorrent vers grab2rss
docker exec qbittorrent ping -c 3 grab2rss

# Test 2 : Accès HTTP depuis qBittorrent
docker exec qbittorrent wget -O- http://grab2rss:8000/health

# Test 3 : Vérifier le flux RSS
docker exec qbittorrent wget -O- http://grab2rss:8000/rss/torrent.json
```

**Résultat attendu** : Tous les tests doivent fonctionner sans erreur.

---

## 📋 Vérification du Réseau

```bash
# Lister les conteneurs sur traefik_proxy
docker network inspect traefik_proxy --format '{{range .Containers}}{{.Name}} {{end}}'

# Devrait afficher au minimum :
# grab2rss qbittorrent
```

---

## 🆘 Dépannage

### Erreur : "network traefik_proxy not found"

```bash
# Le réseau n'existe pas, le créer
docker network create traefik_proxy

# Puis relancer
docker compose up -d
```

### Problème : qBittorrent ne peut pas accéder à grab2rss

```bash
# 1. Vérifier que les deux sont sur le même réseau
docker ps --format "table {{.Names}}\t{{.Networks}}"

# 2. Si qbittorrent n'est pas sur traefik_proxy
docker network connect traefik_proxy qbittorrent

# 3. Tester
docker exec qbittorrent ping grab2rss
```

### Conteneur ne démarre pas

```bash
# Logs détaillés
docker compose logs -f grab2rss

# Vérifier que le réseau existe
docker network ls | grep traefik_proxy
```

---

## ✅ Résultat Final

```
Réseau traefik_proxy
├── grab2rss (port 8000)
├── qbittorrent (port 6881)
├── traefik (proxy)
└── [autres services...]
```

**URL dans qBittorrent** : `http://grab2rss:8000/rss/torrent.json`

---

## 💡 Avantages du Réseau Partagé

- ✅ Tous vos services sur le même réseau
- ✅ Communication facile entre conteneurs
- ✅ Traefik peut gérer le reverse proxy si configuré
- ✅ Gestion centralisée du réseau

---

**Configuration terminée !** 🎉

Vos conteneurs peuvent maintenant communiquer via le réseau `traefik_proxy`.
