# Configuration du flux RSS avec qBittorrent

## Vue d'ensemble

Grabb2RSS génère un flux RSS 2.0 compatible avec qBittorrent, Transmission et ruTorrent. Le système gère automatiquement les URLs selon le contexte d'accès :

- **Accès depuis Docker** (qBittorrent dans un conteneur) : utilise `http://grabb2rss:8000`
- **Accès public/externe** : utilise le domaine configuré

## Format du flux RSS

Le flux généré respecte la spécification RSS 2.0 avec les éléments suivants :

```xml
<?xml version='1.0' encoding='utf-8'?>
<rss version="2.0" xmlns:content="http://purl.org/rss/1.0/modules/content/">
  <channel>
    <title>Grab2RSS</title>
    <link>http://grabb2rss:8000</link>
    <description>Prowlarr to RSS Feed</description>
    <language>fr</language>
    <lastBuildDate>2026-01-20T12:00:00Z</lastBuildDate>
    <ttl>30</ttl>

    <item>
      <title>Nom du torrent</title>
      <pubDate>2026-01-20T10:30:00Z</pubDate>
      <guid isPermaLink="false">grab-123</guid>
      <description>Torrent: Nom du torrent | Tracker: YGGTorrent</description>
      <link>http://grabb2rss:8000/torrents/nom_du_torrent.torrent</link>

      <!-- Balise enclosure OBLIGATOIRE pour qBittorrent -->
      <enclosure
        url="http://grabb2rss:8000/torrents/nom_du_torrent.torrent"
        type="application/x-bittorrent"
        length="12345"/>

      <content:encoded><![CDATA[Nom du torrent]]></content:encoded>
    </item>
  </channel>
</rss>
```

### Éléments clés pour qBittorrent

1. **`<enclosure>`** : Balise OBLIGATOIRE contenant :
   - `url` : URL directe vers le fichier .torrent
   - `type` : DOIT être `application/x-bittorrent`
   - `length` : Taille du fichier en octets (optionnel mais recommandé)

2. **Encodage des URLs** : Tous les caractères spéciaux sont encodés automatiquement

## Configuration dans Docker

### 1. Configuration de Grabb2RSS

#### Fichier `.env` ou `/config/settings.yml`

```env
# URL interne Docker (pour qBittorrent dans le réseau Docker)
RSS_INTERNAL_URL=http://grabb2rss:8000

# Domaine public (pour accès externe)
RSS_DOMAIN=rss.votredomaine.com
RSS_SCHEME=https

# Métadonnées du flux
RSS_TITLE=Mes Torrents
RSS_DESCRIPTION=Flux RSS Prowlarr
```

#### Comment ça fonctionne ?

Le système détecte automatiquement le contexte :

- **Requête avec Host = `grabb2rss`, `localhost`, `127.0.0.1`** → utilise `RSS_INTERNAL_URL`
- **Requête avec un autre Host** → utilise `RSS_SCHEME://RSS_DOMAIN`

### 2. Configuration Docker Compose

Assurez-vous que les conteneurs sont sur le même réseau :

```yaml
version: "3.8"

services:
  grabb2rss:
    image: ghcr.io/kesurof/grabb2rss:latest
    container_name: grabb2rss
    networks:
      - media
    ports:
      - "8000:8000"
    volumes:
      - ./config:/config
      - ./data:/app/data
    environment:
      - RSS_INTERNAL_URL=http://grabb2rss:8000
      - RSS_DOMAIN=rss.votredomaine.com
      - RSS_SCHEME=https

  qbittorrent:
    image: lscr.io/linuxserver/qbittorrent:latest
    container_name: qbittorrent
    networks:
      - media
    ports:
      - "8080:8080"
    volumes:
      - ./qbittorrent/config:/config
      - ./downloads:/downloads

networks:
  media:
    driver: bridge
```

### 3. Configuration dans qBittorrent

#### Via l'interface Web

1. **Accéder à qBittorrent** : `http://localhost:8080`

2. **Ouvrir les paramètres** : `Tools` → `Options` → `RSS`

3. **Activer le lecteur RSS** : Cocher `Enable fetching RSS feeds`

4. **Ajouter un nouveau flux** :
   - Clic droit sur `RSS Feeds` → `New subscription`
   - **URL** : `http://grabb2rss:8000/rss` (ou `/rss.xml`)
   - **Nom** : `Prowlarr - Tous les torrents`

5. **Filtrer par tracker** (optionnel) :
   - URL : `http://grabb2rss:8000/rss/tracker/NomDuTracker`
   - Exemple : `http://grabb2rss:8000/rss/tracker/YGGTorrent`

6. **Configurer le téléchargement automatique** :
   - Clic droit sur le flux → `RSS Downloader`
   - Créer une règle de filtrage selon vos besoins

#### Vérification

Dans qBittorrent, vous devriez voir :
- Le flux apparaître dans la liste RSS
- Les torrents se charger automatiquement
- Le nombre d'articles non lus

### 4. Formats d'URL disponibles

#### Flux global (tous les trackers)

- **XML** : `http://grabb2rss:8000/rss`
- **XML (alias)** : `http://grabb2rss:8000/rss.xml`
- **JSON** : `http://grabb2rss:8000/rss/torrent.json`

#### Flux filtré par tracker

- **XML** : `http://grabb2rss:8000/rss/tracker/{nom_tracker}`
- **JSON** : `http://grabb2rss:8000/rss/tracker/{nom_tracker}/json`

Exemples :
- `http://grabb2rss:8000/rss/tracker/YGGTorrent`
- `http://grabb2rss:8000/rss/tracker/Torrent9`

### 5. Accès depuis l'extérieur de Docker

Si vous accédez au flux depuis un client qui n'est PAS dans Docker :

```
https://rss.votredomaine.com/rss
```

Le système utilisera automatiquement le domaine public configuré dans `RSS_DOMAIN`.

## Tests et débogage

### Tester le flux RSS

#### Depuis le terminal (dans le conteneur)

```bash
curl http://grabb2rss:8000/rss
```

#### Depuis le navigateur

```
http://localhost:8000/rss
```

### Vérifier le format XML

Le flux doit :
- Commencer par `<?xml version='1.0' encoding='utf-8'?>`
- Contenir une balise `<rss version="2.0">`
- Avoir des balises `<enclosure>` avec `type="application/x-bittorrent"`

### Logs qBittorrent

Pour voir les logs d'importation RSS :

1. Options → Advanced → Enable logging
2. Vérifier les logs dans `/config/logs/`

## Compatibilité

### Clients testés

- ✅ **qBittorrent** v4.3+
- ✅ **Transmission** v3.0+
- ✅ **ruTorrent** v3.10+

### Spécifications

- ✅ RSS 2.0
- ✅ Encodage UTF-8
- ✅ Enclosure avec type MIME correct
- ✅ URLs encodées (support caractères spéciaux)
- ✅ Namespaces XML (content:encoded)

## Dépannage

### Le flux ne s'affiche pas dans qBittorrent

1. **Vérifier la connectivité réseau** :
   ```bash
   docker exec -it qbittorrent ping grabb2rss
   ```

2. **Vérifier que les conteneurs sont sur le même réseau** :
   ```bash
   docker network inspect media
   ```

3. **Tester l'URL manuellement** :
   ```bash
   docker exec -it qbittorrent curl http://grabb2rss:8000/rss
   ```

### Les torrents ne se téléchargent pas automatiquement

1. Vérifier que `Enable fetching RSS feeds` est activé
2. Vérifier que le RSS Downloader a une règle configurée
3. Vérifier que les filtres correspondent aux titres des torrents

### Erreur 404 ou 500

1. Vérifier que Grabb2RSS est démarré :
   ```bash
   docker logs grabb2rss
   ```

2. Vérifier la configuration dans `/config/settings.yml`

3. Vérifier que des torrents ont été synchronisés :
   ```bash
   curl http://localhost:8000/api/stats
   ```

## Sécurité

### Authentification

Le flux RSS est **public par défaut**. Pour sécuriser l'accès :

1. **Utiliser un reverse proxy** (Traefik, Nginx) avec authentification
2. **Limiter l'accès réseau** au réseau Docker interne
3. **Utiliser HTTPS** pour l'accès externe

### Exemple avec Traefik

```yaml
labels:
  - "traefik.enable=true"
  - "traefik.http.routers.grabb2rss.rule=Host(`rss.votredomaine.com`)"
  - "traefik.http.routers.grabb2rss.middlewares=auth"
  - "traefik.http.middlewares.auth.basicauth.users=user:$$apr1$$..."
```

## Performance

### Recommandations

- **TTL** : Le flux a un TTL de 30 minutes (configurable)
- **Limite d'items** : Par défaut 100 items maximum par flux
- **Intervalle de sync** : Configurer qBittorrent pour vérifier le flux toutes les 30 minutes minimum

### Optimisation

Pour réduire la charge :

1. Utiliser des flux filtrés par tracker plutôt que le flux global
2. Configurer `RETENTION_HOURS` pour limiter l'historique
3. Utiliser `AUTO_PURGE=true` pour nettoyer automatiquement
