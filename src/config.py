# config.py
import os
import logging
from pathlib import Path
import yaml
from typing import Optional
from paths import PROJECT_ROOT, CONFIG_DIR, SETTINGS_FILE, DATA_DIR, TORRENT_DIR

logger = logging.getLogger(__name__)

def _resolve_settings_paths() -> tuple[Path, Path]:
    """Détermine le chemin settings.yml en tenant compte du contexte CI."""
    if os.getenv("CI", "").lower() == "true":
        settings_file = PROJECT_ROOT / ".ci" / "config" / "settings.yml"
        return settings_file, settings_file.parent

    return SETTINGS_FILE, CONFIG_DIR

# Fonction pour créer le fichier settings.yml par défaut
def create_default_settings():
    """Crée un fichier settings.yml par défaut si il n'existe pas"""
    settings_file, config_dir = _resolve_settings_paths()

    # Créer le répertoire de config si nécessaire
    try:
        config_dir.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        logger.warning("Erreur création répertoire config: %s", e)
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
            "description": "Prowlarr to RSS Feed",
            "allowed_hosts": []
        },
        "cors": {
            "allow_origins": [
                "http://localhost:8000",
                "http://127.0.0.1:8000"
            ]
        },
        "torrents": {
            "expose_static": False
        },
        "network": {
            "retries": 3,
            "backoff_seconds": 1.0,
            "timeout_seconds": 10
        },
        "torrents_download": {
            "max_size_mb": 50
        },
        "logging": {
            "level": "INFO"
        },
        "auth": {
            "enabled": False,
            "username": "",
            "password_hash": "",
            "api_keys": [],
            "cookie_secure": False
        },
        "setup_completed": False
    }

    try:
        with open(settings_file, 'w', encoding='utf-8') as f:
            yaml.dump(default_config, f, default_flow_style=False, allow_unicode=True)
        logger.info("Configuration par défaut créée: %s", settings_file)
        return True
    except Exception as e:
        logger.error("Erreur création settings.yml: %s", e)
        return False

# Fonction pour charger la configuration
def load_configuration():
    """
    Charge la configuration depuis settings.yml
    Crée le fichier par défaut s'il n'existe pas
    """
    config = {}
    settings_file, _ = _resolve_settings_paths()

    # Créer le fichier par défaut si il n'existe pas
    if not settings_file.exists():
        logger.warning("Fichier settings.yml manquant")
        logger.info("Création de la configuration par défaut...")
        create_default_settings()

    # Charger la configuration depuis settings.yml
    try:
        with open(settings_file, 'r', encoding='utf-8') as f:
            yaml_config = yaml.safe_load(f)
            if yaml_config:
                # Validation stricte du settings.yml
                try:
                    from settings_schema import SettingsConfig
                    validated = SettingsConfig.model_validate(yaml_config)
                    yaml_config = validated.model_dump()
                except Exception as e:
                    from pydantic import ValidationError
                    if isinstance(e, ValidationError):
                        logger.error("settings.yml invalide. Détails:")
                        for err in e.errors():
                            loc = ".".join(str(part) for part in err.get("loc", []))
                            msg = err.get("msg", "Erreur de validation")
                            logger.error(" - %s: %s", loc, msg)
                    raise ValueError("settings.yml invalide, corrigez les erreurs avant de démarrer.")

                setup_completed = yaml_config.get("setup_completed", False)

                if setup_completed:
                    logger.info("Configuration chargée depuis %s", settings_file)
                else:
                    logger.info("Mode Setup Wizard - Configuration à effectuer via l'interface web")

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
                config["RSS_ALLOWED_HOSTS"] = rss.get("allowed_hosts", [])

                cors = yaml_config.get("cors", {})
                config["CORS_ALLOW_ORIGINS"] = cors.get("allow_origins", [])

                torrents = yaml_config.get("torrents", {})
                config["TORRENTS_EXPOSE_STATIC"] = torrents.get("expose_static", False)

                network = yaml_config.get("network", {})
                config["NETWORK_RETRIES"] = network.get("retries", 3)
                config["NETWORK_BACKOFF_SECONDS"] = network.get("backoff_seconds", 1.0)
                config["NETWORK_TIMEOUT_SECONDS"] = network.get("timeout_seconds", 10)

                torrents_download = yaml_config.get("torrents_download", {})
                config["TORRENTS_MAX_SIZE_MB"] = torrents_download.get("max_size_mb", 50)

                logging_cfg = yaml_config.get("logging", {})
                config["LOG_LEVEL"] = logging_cfg.get("level", "INFO")
    except Exception as e:
        logger.error("Erreur lecture %s: %s", settings_file, e)
        logger.error("Le fichier settings.yml est invalide. Corrigez-le pour démarrer.")
        raise

    return config

# Charger la configuration (initialisé vide, rempli par reload_config)
_loaded_config: dict = {}

# Helper pour récupérer une valeur avec fallback
def _get_config(key: str, default: any, convert_type: type = str):
    """Récupère une config depuis YAML avec fallback"""
    if key in _loaded_config:
        value = _loaded_config[key]
        if convert_type == bool and isinstance(value, str):
            return value.lower() == "true"
        return convert_type(value) if value else default

    return default

def _get_list_config(key: str, default: list[str]) -> list[str]:
    """Récupère une config liste depuis YAML avec fallback"""
    if key in _loaded_config:
        value = _loaded_config[key]
        if isinstance(value, list):
            return [str(v) for v in value if str(v).strip()]
        if isinstance(value, str):
            return [v.strip() for v in value.split(",") if v.strip()]
    return default

def _get_env_list(env_key: str) -> Optional[list[str]]:
    """Parse une liste depuis une variable d'environnement (séparée par virgules)."""
    value = os.getenv(env_key)
    if value is None:
        return None
    return [v.strip() for v in value.split(",") if v.strip()]

def _get_env_bool(env_key: str) -> Optional[bool]:
    """Parse un booléen depuis une variable d'environnement."""
    value = os.getenv(env_key)
    if value is None:
        return None
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}

def _get_env_int(env_key: str) -> Optional[int]:
    """Parse un entier depuis une variable d'environnement."""
    value = os.getenv(env_key)
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        return None

def _get_env_float(env_key: str) -> Optional[float]:
    """Parse un float depuis une variable d'environnement."""
    value = os.getenv(env_key)
    if value is None:
        return None
    try:
        return float(value)
    except ValueError:
        return None

def reload_config():
    """Recharge la configuration depuis settings.yml et met à jour les variables globales"""
    global _loaded_config
    global PROWLARR_URL, PROWLARR_API_KEY, PROWLARR_HISTORY_PAGE_SIZE
    global RADARR_URL, RADARR_API_KEY, RADARR_ENABLED
    global SONARR_URL, SONARR_API_KEY, SONARR_ENABLED
    global RETENTION_HOURS, AUTO_PURGE, DEDUP_HOURS, SYNC_INTERVAL
    global RSS_DOMAIN, RSS_SCHEME, RSS_INTERNAL_URL, RSS_ALLOWED_HOSTS
    global RSS_TITLE, RSS_DESCRIPTION
    global CORS_ALLOW_ORIGINS
    global TORRENTS_EXPOSE_STATIC
    global NETWORK_RETRIES, NETWORK_BACKOFF_SECONDS, NETWORK_TIMEOUT_SECONDS
    global TORRENTS_MAX_SIZE_MB
    global LOG_LEVEL

    logger.info("Rechargement de la configuration depuis settings.yml...")

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
    env_rss_allowed = _get_env_list("RSS_ALLOWED_HOSTS")
    RSS_ALLOWED_HOSTS = env_rss_allowed if env_rss_allowed is not None else _get_list_config(
        "RSS_ALLOWED_HOSTS",
        []
    )

    RSS_TITLE = _get_config("RSS_TITLE", "grabb2rss", str)
    RSS_DESCRIPTION = _get_config("RSS_DESCRIPTION", "Derniers torrents grabbés via Prowlarr", str)

    env_cors = _get_env_list("CORS_ALLOW_ORIGINS")
    CORS_ALLOW_ORIGINS = env_cors if env_cors is not None else _get_list_config(
        "CORS_ALLOW_ORIGINS",
        ["http://localhost:8000", "http://127.0.0.1:8000"]
    )

    env_torrents_expose = _get_env_bool("TORRENTS_EXPOSE_STATIC")
    TORRENTS_EXPOSE_STATIC = env_torrents_expose if env_torrents_expose is not None else _get_config(
        "TORRENTS_EXPOSE_STATIC",
        False,
        bool
    )

    env_network_retries = _get_env_int("NETWORK_RETRIES")
    NETWORK_RETRIES = env_network_retries if env_network_retries is not None else _get_config(
        "NETWORK_RETRIES",
        3,
        int
    )
    env_network_backoff = _get_env_float("NETWORK_BACKOFF_SECONDS")
    NETWORK_BACKOFF_SECONDS = env_network_backoff if env_network_backoff is not None else _get_config(
        "NETWORK_BACKOFF_SECONDS",
        1.0,
        float
    )
    env_network_timeout = _get_env_float("NETWORK_TIMEOUT_SECONDS")
    NETWORK_TIMEOUT_SECONDS = env_network_timeout if env_network_timeout is not None else _get_config(
        "NETWORK_TIMEOUT_SECONDS",
        10,
        float
    )

    env_torrents_max_size = _get_env_int("TORRENTS_MAX_SIZE_MB")
    TORRENTS_MAX_SIZE_MB = env_torrents_max_size if env_torrents_max_size is not None else _get_config(
        "TORRENTS_MAX_SIZE_MB",
        50,
        int
    )

    env_log_level = os.getenv("LOG_LEVEL")
    LOG_LEVEL = env_log_level if env_log_level else _get_config("LOG_LEVEL", "INFO", str)

    logger.info("Configuration rechargée")
    logger.info("Prowlarr URL: %s", PROWLARR_URL)
    logger.info("Sync interval: %ss", SYNC_INTERVAL)
    logger.info("RSS domain: %s", RSS_DOMAIN)

    return True

# Chemins
DATA_DIR = Path(os.getenv("DATA_DIR", str(DATA_DIR)))
DB_PATH = DATA_DIR / "grabs.db"
TORRENT_DIR = DATA_DIR / "torrents"

# Créer les répertoires avec permissions appropriées
try:
    DATA_DIR.mkdir(mode=0o755, exist_ok=True, parents=True)
    DB_PATH.parent.mkdir(mode=0o755, exist_ok=True, parents=True)
    TORRENT_DIR.mkdir(mode=0o755, exist_ok=True, parents=True)
    logger.info("Répertoires créés/vérifiés")
    logger.info("DATA_DIR: %s (exists: %s)", DATA_DIR, DATA_DIR.exists())
    logger.info("TORRENT_DIR: %s (exists: %s)", TORRENT_DIR, TORRENT_DIR.exists())
except Exception as e:
    logger.warning("Erreur lors de la création des répertoires: %s", e)
    logger.info("Vérifiez les permissions sur %s", DATA_DIR.parent)

# Web
APP_HOST = os.getenv("APP_HOST", "0.0.0.0")
APP_PORT = int(os.getenv("APP_PORT", "8000"))

reload_config()

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
    "RSS_INTERNAL_URL": "URL interne complète pour accès Docker (ex: http://grabb2rss:8000)",
    "RSS_ALLOWED_HOSTS": "Liste blanche d'hôtes autorisés pour les URLs RSS (séparés par virgules)",
    "NETWORK_RETRIES": "Nombre de tentatives réseau en cas d'échec",
    "NETWORK_BACKOFF_SECONDS": "Backoff initial en secondes (exponentiel)",
    "NETWORK_TIMEOUT_SECONDS": "Timeout réseau en secondes",
    "TORRENTS_EXPOSE_STATIC": "Exposer /torrents en statique (true/false)",
    "TORRENTS_MAX_SIZE_MB": "Taille max des torrents téléchargés (MB)",
    "LOG_LEVEL": "Niveau de logs (DEBUG, INFO, WARNING, ERROR)"
}

def is_setup_completed() -> bool:
    """Vérifie si le setup wizard a été complété"""
    settings_file, _ = _resolve_settings_paths()
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
