# 🔐 Guide d'authentification Grabb2RSS

Ce guide explique comment configurer et utiliser l'authentification dans Grabb2RSS.

## Vue d'ensemble

Grabb2RSS offre un système d'authentification complet pour sécuriser votre instance :

- **Authentification mono-utilisateur** : Protection de l'interface web par login/mot de passe
- **API Key** : Accès sécurisé aux flux RSS depuis l'extérieur
- **Accès local sans authentification** : Les requêtes depuis le réseau Docker/local fonctionnent sans API key

## Configuration initiale

### 1. Activer l'authentification

Rendez-vous dans l'onglet **⚙️ Configuration** puis dans la section **🔐 Authentification & Sécurité**.

1. Remplissez les champs :
   - **Nom d'utilisateur** : par défaut `admin`
   - **Nouveau mot de passe** : minimum 6 caractères
   - **Confirmer le mot de passe**

2. Cliquez sur **🔒 Activer l'authentification**

3. Une API key sera automatiquement générée et affichée

4. L'application va recharger et vous demander de vous connecter

### 2. Première connexion

Après activation, vous serez redirigé vers la page de connexion :

1. Entrez votre nom d'utilisateur et mot de passe
2. Cliquez sur **Se connecter**
3. Vous êtes maintenant authentifié pour 24 heures

## Utilisation des flux RSS

### Accès local (Docker/réseau interne)

Si vous accédez aux flux RSS depuis le même réseau Docker ou depuis localhost, **aucune authentification n'est requise**.

**Exemples d'accès local :**
```
http://grabb2rss:8000/rss
http://localhost:8000/rss
http://127.0.0.1:8000/rss
http://192.168.x.x:8000/rss (réseau privé)
```

### Accès externe (Internet)

Pour accéder aux flux RSS depuis l'extérieur, vous devez utiliser votre **API key** :

**Format :**
```
http://votre-domaine.com/rss?api_key=VOTRE_CLE_API
```

**Exemples :**
```
# Flux global
https://grabb2rss.example.com/rss?api_key=abc123...

# Flux par tracker
https://grabb2rss.example.com/rss/tracker/YGGTorrent?api_key=abc123...

# Format JSON
https://grabb2rss.example.com/rss/torrent.json?api_key=abc123...
```

### Configuration dans qBittorrent

1. Allez dans **Outils** → **Options** → **RSS**
2. Activez le lecteur RSS
3. Ajoutez un nouveau flux RSS :
   - **URL** : `http://grabb2rss:8000/rss` (si dans Docker)
   - **URL** : `https://votre-domaine.com/rss?api_key=VOTRE_CLE` (si externe)

## Gestion de l'API Key

### Afficher votre API key

1. Connectez-vous à l'interface web
2. Allez dans **⚙️ Configuration**
3. Scrollez jusqu'à **🔑 API Key**
4. Votre clé est affichée

### Copier l'API key

Cliquez sur **📋 Copier** pour copier la clé dans le presse-papiers.

### Générer une nouvelle API key

1. Allez dans **⚙️ Configuration** → **🔑 API Key**
2. Cliquez sur **🔄 Générer une nouvelle API Key**
3. Confirmez (⚠️ l'ancienne clé ne fonctionnera plus)
4. Mettez à jour vos clients RSS avec la nouvelle clé

## Déconnexion

Pour vous déconnecter :

1. Cliquez sur **🚪 Déconnexion** dans le header
2. Confirmez
3. Vous serez redirigé vers la page de connexion

## Configuration avancée

### Modifier le fichier settings.yml

Vous pouvez configurer l'authentification directement dans `/config/settings.yml` :

```yaml
auth:
  enabled: true                    # Activer/désactiver l'auth
  username: "admin"                # Nom d'utilisateur
  password_hash: "..."            # Hash bcrypt du mot de passe
  api_key: "..."                  # API key générée
  require_auth_for_rss: true      # Exiger l'auth pour RSS (sauf local)
```

### Désactiver l'authentification pour les flux RSS

Si vous souhaitez que les flux RSS soient accessibles sans authentification (même depuis l'extérieur), modifiez `settings.yml` :

```yaml
auth:
  enabled: true
  require_auth_for_rss: false     # ⚠️ RSS accessible sans auth
```

### Réinitialiser le mot de passe

Si vous avez oublié votre mot de passe :

1. Arrêtez le conteneur
2. Éditez `/config/settings.yml`
3. Changez `auth.enabled` à `false`
4. Redémarrez le conteneur
5. Reconfigurez un nouveau mot de passe via l'interface

## Sécurité

### Bonnes pratiques

- ✅ Utilisez un mot de passe fort (minimum 12 caractères recommandés)
- ✅ Changez l'API key régulièrement
- ✅ Utilisez HTTPS pour les accès externes
- ✅ Ne partagez jamais votre API key publiquement
- ✅ Activez l'authentification si accessible depuis Internet

### Ce qui est protégé

Avec l'authentification activée :
- ✅ Interface web complète
- ✅ Toutes les routes `/api/*`
- ✅ Flux RSS (sauf accès local)
- ✅ Fichiers torrents `/torrents/*`

### Ce qui reste public

- `/health` - Health check
- `/setup` - Setup wizard (premier lancement uniquement)
- `/login` - Page de connexion

## Exemples d'utilisation

### Script Python avec API key

```python
import requests

API_KEY = "votre_api_key_ici"
BASE_URL = "https://grabb2rss.example.com"

# Récupérer le flux RSS
response = requests.get(f"{BASE_URL}/rss?api_key={API_KEY}")
print(response.text)

# Récupérer les stats (requiert API key dans le header)
headers = {"X-API-Key": API_KEY}
response = requests.get(f"{BASE_URL}/api/stats", headers=headers)
print(response.json())
```

### Curl avec API key

```bash
# Flux RSS
curl "https://grabb2rss.example.com/rss?api_key=VOTRE_CLE"

# API avec header
curl -H "X-API-Key: VOTRE_CLE" "https://grabb2rss.example.com/api/stats"
```

## Troubleshooting

### "401 Non authentifié"

- Vérifiez que votre API key est correcte
- Assurez-vous d'ajouter `?api_key=VOTRE_CLE` à l'URL
- Pour les requêtes locales, vérifiez que vous utilisez `localhost` ou l'IP du réseau Docker

### "Identifiants incorrects"

- Vérifiez votre nom d'utilisateur et mot de passe
- Respectez la casse (majuscules/minuscules)
- Réinitialisez le mot de passe si nécessaire (voir ci-dessus)

### L'authentification ne s'active pas

- Vérifiez les logs du conteneur
- Assurez-vous que le fichier `/config/settings.yml` est accessible en écriture
- Redémarrez le conteneur après modification manuelle de la config

## Support

Pour plus d'aide :
- Consultez les [Issues GitHub](https://github.com/kesurof/grabb2rss/issues)
- Vérifiez les logs : `docker logs grabb2rss`
