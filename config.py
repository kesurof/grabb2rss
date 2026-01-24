# config.py
import os
from pathlib import Path
import yaml

# Fonction pour créer le fichier settings.yml par défaut
def create_default_settings():
    """Crée un fichier settings.yml par défaut si il n'existe pas"""
    settings_file = Path("/config/settings.yml")
    config_dir = Path("/config")

    # Créer le répertoire /config si nécessaire
    try:
        config_dir.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        print(f"⚠️  Erreur création répertoire /config: {e}")
        return False

    # Créer le fichier settings.yml par défaut
    default_config = {
        "prowlarr": {
            "url": "",
            "api_key": "",
            "history_page_size": 500
        },
        "radarr": {
            "url": "",
            "api_key": "",
            "enabled": True
        },
        "sonarr": {
            "url": "",
            "api_key": "",
            "enabled": True
        },
        "sync": {
            "interval": 3600,
            "retention_hours": 168,
            "dedup_hours": 168,
            "auto_purge": True
        },
        "rss": {
            "domain": "localhost:8000",
            "scheme": "http",
            "title": "Grabb2RSS",
            "description": "Prowlarr to RSS Feed"
        },
        "setup_completed": False
    }

    try:
        with open(settings_file, 'w', encoding='utf-8') as f:
            yaml.dump(default_config, f, default_flow_style=False, allow_unicode=True)
        print(f"✅ Configuration par défaut créée: {settings_file}")
        return True
    except Exception as e:
        print(f"❌ Erreur création settings.yml: {e}")
        return False

# Fonction pour charger la configuration
def load_configuration():
    """
    Charge la configuration depuis /config/settings.yml
    Crée le fichier par défaut s'il n'existe pas
    """
    config = {}
    settings_file = Path("/config/settings.yml")

    # Créer le fichier par défaut si il n'existe pas
    if not settings_file.exists():
        print(f"⚠️  Fichier settings.yml manquant")
        print(f"💡 Création de la configuration par défaut...")
        create_default_settings()

    # Charger la configuration depuis settings.yml
    try:
        with open(settings_file, 'r', encoding='utf-8') as f:
            yaml_config = yaml.safe_load(f)
            if yaml_config:
                setup_completed = yaml_config.get("setup_completed", False)

                if setup_completed:
                    print(f"✅ Configuration chargée depuis {settings_file}")
                else:
                    print(f"⚙️  Mode Setup Wizard - Configuration à effectuer via l'interface web")

                # Mapper la config YAML vers les variables
                prowlarr = yaml_config.get("prowlarr", {})
                config["PROWLARR_URL"] = prowlarr.get("url", "")
                config["PROWLARR_API_KEY"] = prowlarr.get("api_key", "")
                config["PROWLARR_HISTORY_PAGE_SIZE"] = prowlarr.get("history_page_size", 500)

                radarr = yaml_config.get("radarr", {})
                config["RADARR_URL"] = radarr.get("url", "")
                config["RADARR_API_KEY"] = radarr.get("api_key", "")
                config["RADARR_ENABLED"] = radarr.get("enabled", True)

                sonarr = yaml_config.get("sonarr", {})
                config["SONARR_URL"] = sonarr.get("url", "")
                config["SONARR_API_KEY"] = sonarr.get("api_key", "")
                config["SONARR_ENABLED"] = sonarr.get("enabled", True)

                sync = yaml_config.get("sync", {})
                config["SYNC_INTERVAL"] = sync.get("interval", 3600)
                config["RETENTION_HOURS"] = sync.get("retention_hours", 168)
                config["AUTO_PURGE"] = sync.get("auto_purge", True)
                config["DEDUP_HOURS"] = sync.get("dedup_hours", 168)

                rss = yaml_config.get("rss", {})
                config["RSS_DOMAIN"] = rss.get("domain", "localhost:8000")
                config["RSS_SCHEME"] = rss.get("scheme", "http")
                config["RSS_TITLE"] = rss.get("title", "Grabb2RSS")
                config["RSS_DESCRIPTION"] = rss.get("description", "Prowlarr to RSS Feed")
    except Exception as e:
        print(f"⚠️  Erreur lecture {settings_file}: {e}")
        print(f"💡 Utilisation de la configuration par défaut")

    return config

# Charger la configuration
_loaded_config = load_configuration()

# Helper pour récupérer une valeur avec fallback
def _get_config(key: str, default: any, convert_type: type = str):
    """Récupère une config depuis YAML avec fallback"""
    if key in _loaded_config:
        value = _loaded_config[key]
        if convert_type == bool and isinstance(value, str):
            return value.lower() == "true"
        return convert_type(value) if value else default

    return default

def reload_config():
    """Recharge la configuration depuis settings.yml et met à jour les variables globales"""
    global _loaded_config
    global PROWLARR_URL, PROWLARR_API_KEY, PROWLARR_HISTORY_PAGE_SIZE
    global RADARR_URL, RADARR_API_KEY, RADARR_ENABLED
    global SONARR_URL, SONARR_API_KEY, SONARR_ENABLED
    global RETENTION_HOURS, AUTO_PURGE, DEDUP_HOURS, SYNC_INTERVAL
    global RSS_DOMAIN, RSS_SCHEME, RSS_INTERNAL_URL
    global RSS_TITLE, RSS_DESCRIPTION

    print("🔄 Rechargement de la configuration depuis settings.yml...")

    # Recharger le dict
    _loaded_config = load_configuration()

    # Mettre à jour toutes les variables globales
    PROWLARR_URL = _get_config("PROWLARR_URL", "http://localhost:9696", str)
    PROWLARR_API_KEY = _get_config("PROWLARR_API_KEY", "", str)
    PROWLARR_HISTORY_PAGE_SIZE = _get_config("PROWLARR_HISTORY_PAGE_SIZE", 100, int)

    RADARR_URL = _get_config("RADARR_URL", "", str)
    RADARR_API_KEY = _get_config("RADARR_API_KEY", "", str)
    RADARR_ENABLED = _get_config("RADARR_ENABLED", False, bool)

    SONARR_URL = _get_config("SONARR_URL", "", str)
    SONARR_API_KEY = _get_config("SONARR_API_KEY", "", str)
    SONARR_ENABLED = _get_config("SONARR_ENABLED", False, bool)

    RETENTION_HOURS = _get_config("RETENTION_HOURS", 168, int) or None
    AUTO_PURGE = _get_config("AUTO_PURGE", True, bool)
    DEDUP_HOURS = _get_config("DEDUP_HOURS", 168, int)
    SYNC_INTERVAL = _get_config("SYNC_INTERVAL", 3600, int)

    RSS_DOMAIN = _get_config("RSS_DOMAIN", "localhost:8000", str)
    RSS_SCHEME = _get_config("RSS_SCHEME", "http", str)
    RSS_INTERNAL_URL = _get_config("RSS_INTERNAL_URL", "http://grabb2rss:8000", str)

    RSS_TITLE = _get_config("RSS_TITLE", "grabb2rss", str)
    RSS_DESCRIPTION = _get_config("RSS_DESCRIPTION", "Derniers torrents grabbés via Prowlarr", str)

    print(f"✅ Configuration rechargée:")
    print(f"   - Prowlarr URL: {PROWLARR_URL}")
    print(f"   - Sync interval: {SYNC_INTERVAL}s")
    print(f"   - RSS domain: {RSS_DOMAIN}")

    return True

# Chemins
DATA_DIR = Path(os.getenv("DATA_DIR", "/app/data"))
DB_PATH = DATA_DIR / "grabs.db"
TORRENT_DIR = DATA_DIR / "torrents"

# Créer les répertoires avec permissions appropriées
try:
    DATA_DIR.mkdir(mode=0o755, exist_ok=True, parents=True)
    DB_PATH.parent.mkdir(mode=0o755, exist_ok=True, parents=True)
    TORRENT_DIR.mkdir(mode=0o777, exist_ok=True, parents=True)
    print(f"✅ Répertoires créés/vérifiés:")
    print(f"   - DATA_DIR: {DATA_DIR} (exists: {DATA_DIR.exists()})")
    print(f"   - TORRENT_DIR: {TORRENT_DIR} (exists: {TORRENT_DIR.exists()})")
except Exception as e:
    print(f"⚠️  Erreur lors de la création des répertoires: {e}")
    print(f"💡 Vérifiez les permissions sur {DATA_DIR.parent}")


# Prowlarr
PROWLARR_URL = _get_config("PROWLARR_URL", "http://localhost:9696", str)
PROWLARR_API_KEY = _get_config("PROWLARR_API_KEY", "", str)
PROWLARR_HISTORY_PAGE_SIZE = _get_config("PROWLARR_HISTORY_PAGE_SIZE", 100, int)

# Radarr (optionnel)
RADARR_URL = _get_config("RADARR_URL", "", str)
RADARR_API_KEY = _get_config("RADARR_API_KEY", "", str)
RADARR_ENABLED = _get_config("RADARR_ENABLED", False, bool)

# Sonarr (optionnel)
SONARR_URL = _get_config("SONARR_URL", "", str)
SONARR_API_KEY = _get_config("SONARR_API_KEY", "", str)
SONARR_ENABLED = _get_config("SONARR_ENABLED", False, bool)

# Rétention et purge
RETENTION_HOURS = _get_config("RETENTION_HOURS", 168, int) or None
AUTO_PURGE = _get_config("AUTO_PURGE", True, bool)

# Déduplication
DEDUP_HOURS = _get_config("DEDUP_HOURS", 168, int)

# Scheduler
SYNC_INTERVAL = _get_config("SYNC_INTERVAL", 3600, int)

# Web
APP_HOST = os.getenv("APP_HOST", "0.0.0.0")
APP_PORT = int(os.getenv("APP_PORT", "8000"))

# Multi-domaine
RSS_DOMAIN = _get_config("RSS_DOMAIN", "localhost:8000", str)
RSS_SCHEME = _get_config("RSS_SCHEME", "http", str)

# URL interne Docker (pour accès depuis d'autres conteneurs)
RSS_INTERNAL_URL = _get_config("RSS_INTERNAL_URL", "http://grabb2rss:8000", str)

# API
RSS_TITLE = _get_config("RSS_TITLE", "grabb2rss", str)
RSS_DESCRIPTION = _get_config("RSS_DESCRIPTION", "Derniers torrents grabbés via Prowlarr", str)

# Descriptions pour l'UI
DESCRIPTIONS = {
    "PROWLARR_URL": "URL de votre serveur Prowlarr (ex: http://localhost:9696)",
    "PROWLARR_API_KEY": "Clé API Prowlarr (obtenue depuis Prowlarr Settings → API)",
    "PROWLARR_HISTORY_PAGE_SIZE": "Nombre d'enregistrements à récupérer par sync (50-500)",
    "SYNC_INTERVAL": "Intervalle entre chaque sync en secondes (3600 = 1 heure)",
    "RETENTION_HOURS": "Nombre d'heures avant suppression automatique (168 = 7j, 0 = infini)",
    "DEDUP_HOURS": "Fenêtre de déduplication en heures (24 = 24h glissant)",
    "AUTO_PURGE": "Activer la suppression automatique des anciens grabs",
    "RSS_DOMAIN": "Domaine pour les URLs RSS publiques (ex: grabb2rss.example.com)",
    "RSS_SCHEME": "Protocole pour les URLs RSS (http ou https)",
    "RSS_INTERNAL_URL": "URL interne complète pour accès Docker (ex: http://grabb2rss:8000)"
}

def is_setup_completed() -> bool:
    """Vérifie si le setup wizard a été complété"""
    settings_file = Path("/config/settings.yml")
    if not settings_file.exists():
        return False

    try:
        import yaml
        with open(settings_file, 'r', encoding='utf-8') as f:
            yaml_config = yaml.safe_load(f)
            return yaml_config and yaml_config.get("setup_completed", False)
    except:
        return False


def validate_config() -> bool:
    """
    Validation simple - ne bloque jamais le démarrage.
    L'application doit pouvoir démarrer même sans configuration.
    """
    return True
