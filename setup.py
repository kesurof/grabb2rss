# setup.py
"""
Module de configuration initiale pour Grabb2RSS
Gère le setup wizard au premier lancement
"""
import yaml
import logging
from pathlib import Path
from typing import Optional, Dict, Any
import requests

# Chemin du fichier de configuration
CONFIG_FILE = Path("/config/settings.yml")
CONFIG_DIR = Path("/config")
logger = logging.getLogger(__name__)

# Configuration par défaut
DEFAULT_CONFIG = {
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
        "auto_purge": True,
        "retention_hours": 168,
        "dedup_hours": 168
    },
    "rss": {
        "domain": "localhost:8000",
        "scheme": "http",
        "title": "Grabb2RSS",
        "description": "Prowlarr to RSS Feed"
    },
    "app": {
        "host": "0.0.0.0",
        "port": 8000
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
    "auth": {
        "enabled": False,
        "username": "",
        "password_hash": "",
        "api_keys": [],
        "cookie_secure": False
    },
    "setup_completed": False
}


def is_first_run() -> bool:
    """Vérifie si c'est le premier lancement (pas de config)"""
    return not CONFIG_FILE.exists() or not load_config().get("setup_completed", False)


def load_config() -> Dict[str, Any]:
    """Charge la configuration depuis le fichier YAML"""
    if not CONFIG_FILE.exists():
        return DEFAULT_CONFIG.copy()

    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
            return config if config else DEFAULT_CONFIG.copy()
    except Exception as e:
        logger.warning("Erreur lecture config: %s", e)
        return DEFAULT_CONFIG.copy()


def save_config(config: Dict[str, Any]) -> bool:
    """Sauvegarde la configuration dans le fichier YAML"""
    try:
        # Créer le répertoire si nécessaire
        logger.info("Création du répertoire: %s", CONFIG_DIR)
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)

        # Vérifier les permissions
        import os
        if CONFIG_DIR.exists():
            logger.info("Répertoire existe: %s", CONFIG_DIR)
            logger.info("Permissions: %s", oct(os.stat(CONFIG_DIR).st_mode)[-3:])
            logger.info("User ID: %s, Group ID: %s", os.getuid(), os.getgid())

        logger.info("Sauvegarde dans: %s", CONFIG_FILE)
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            yaml.dump(config, f, default_flow_style=False, allow_unicode=True)

        logger.info("Configuration sauvegardée: %s", CONFIG_FILE)
        return True
    except PermissionError as e:
        logger.error("Erreur de permissions: %s", e)
        logger.info("Vérifiez que l'utilisateur a les droits d'écriture sur %s", CONFIG_DIR)
        return False
    except Exception as e:
        logger.error("Erreur sauvegarde config: %s", e)
        import traceback
        traceback.print_exc()
        return False


def update_config(new_config: Dict[str, Any]) -> bool:
    """Met à jour la configuration avec les nouvelles valeurs"""
    config = load_config()

    # Merge deep
    def deep_merge(base: dict, update: dict) -> dict:
        for key, value in update.items():
            if isinstance(value, dict) and key in base and isinstance(base[key], dict):
                base[key] = deep_merge(base[key], value)
            else:
                base[key] = value
        return base

    config = deep_merge(config, new_config)
    return save_config(config)


def mark_setup_completed() -> bool:
    """Marque le setup comme complété"""
    config = load_config()
    config["setup_completed"] = True
    return save_config(config)


def get_config_value(key_path: str, default: Any = None) -> Any:
    """
    Récupère une valeur de config par chemin (ex: 'prowlarr.url')
    """
    config = load_config()
    keys = key_path.split('.')

    value = config
    for key in keys:
        if isinstance(value, dict) and key in value:
            value = value[key]
        else:
            return default

    return value


def validate_prowlarr_config(url: str, api_key: str) -> tuple[bool, Optional[str]]:
    """Valide la configuration Prowlarr en testant la connexion"""
    if not url or not api_key:
        return False, "URL et clé API requis"

    try:
        from network import request_with_retries
        response = request_with_retries(
            "GET",
            f"{url}/api/v1/health",
            headers={"X-Api-Key": api_key}
        )
        if response.status_code == 200:
            return True, None
        else:
            return False, f"Erreur HTTP {response.status_code}"
    except requests.exceptions.ConnectionError:
        return False, "Impossible de se connecter à Prowlarr"
    except requests.exceptions.Timeout:
        return False, "Timeout de connexion"
    except Exception as e:
        logger.warning("Erreur validation Prowlarr: %s", e)
        return False, "Erreur de validation Prowlarr"


def create_initial_config_if_needed():
    """Crée un fichier de config initial si nécessaire"""
    if not CONFIG_FILE.exists():
        logger.info("Création de la configuration initiale...")
        save_config(DEFAULT_CONFIG)


def get_config_for_ui() -> Dict[str, Any]:
    """
    Récupère la configuration au format attendu par l'UI
    Retourne un dict avec {key: {value: ..., description: ...}}
    """
    config = load_config()

    # Descriptions pour l'UI
    descriptions = {
        "prowlarr_url": "URL de votre serveur Prowlarr (ex: http://prowlarr:9696)",
        "prowlarr_api_key": "Clé API Prowlarr (obtenue depuis Prowlarr Settings → API)",
        "prowlarr_history_page_size": "Nombre d'enregistrements à récupérer par sync (50-500)",
        "radarr_url": "URL de Radarr (ex: http://radarr:7878)",
        "radarr_api_key": "Clé API Radarr",
        "radarr_enabled": "Activer l'intégration Radarr (true/false)",
        "sonarr_url": "URL de Sonarr (ex: http://sonarr:8989)",
        "sonarr_api_key": "Clé API Sonarr",
        "sonarr_enabled": "Activer l'intégration Sonarr (true/false)",
        "sync_interval": "Intervalle entre chaque sync en secondes (3600 = 1 heure)",
        "sync_retention_hours": "Nombre d'heures avant suppression automatique (168 = 7j, 0 = infini)",
        "sync_dedup_hours": "Fenêtre de déduplication en heures (24 = 24h glissant)",
        "sync_auto_purge": "Activer la suppression automatique des anciens grabs (true/false)",
        "rss_domain": "Domaine pour les URLs RSS (ex: grabb2rss.example.com)",
        "rss_scheme": "Protocole pour les URLs RSS (http ou https)",
        "rss_title": "Titre du flux RSS",
        "rss_description": "Description du flux RSS"
    }

    # Convertir la config YAML en format UI
    ui_config = {}

    # Prowlarr
    prowlarr = config.get("prowlarr", {})
    ui_config["prowlarr_url"] = {
        "value": prowlarr.get("url", ""),
        "description": descriptions.get("prowlarr_url", "")
    }
    ui_config["prowlarr_api_key"] = {
        "value": prowlarr.get("api_key", ""),
        "description": descriptions.get("prowlarr_api_key", "")
    }
    ui_config["prowlarr_history_page_size"] = {
        "value": str(prowlarr.get("history_page_size", 500)),
        "description": descriptions.get("prowlarr_history_page_size", "")
    }

    # Radarr
    radarr = config.get("radarr", {})
    ui_config["radarr_url"] = {
        "value": radarr.get("url", ""),
        "description": descriptions.get("radarr_url", "")
    }
    ui_config["radarr_api_key"] = {
        "value": radarr.get("api_key", ""),
        "description": descriptions.get("radarr_api_key", "")
    }
    ui_config["radarr_enabled"] = {
        "value": str(radarr.get("enabled", True)).lower(),
        "description": descriptions.get("radarr_enabled", "")
    }

    # Sonarr
    sonarr = config.get("sonarr", {})
    ui_config["sonarr_url"] = {
        "value": sonarr.get("url", ""),
        "description": descriptions.get("sonarr_url", "")
    }
    ui_config["sonarr_api_key"] = {
        "value": sonarr.get("api_key", ""),
        "description": descriptions.get("sonarr_api_key", "")
    }
    ui_config["sonarr_enabled"] = {
        "value": str(sonarr.get("enabled", True)).lower(),
        "description": descriptions.get("sonarr_enabled", "")
    }

    # Sync
    sync = config.get("sync", {})
    ui_config["sync_interval"] = {
        "value": str(sync.get("interval", 3600)),
        "description": descriptions.get("sync_interval", "")
    }
    ui_config["sync_retention_hours"] = {
        "value": str(sync.get("retention_hours", 168)),
        "description": descriptions.get("sync_retention_hours", "")
    }
    ui_config["sync_dedup_hours"] = {
        "value": str(sync.get("dedup_hours", 168)),
        "description": descriptions.get("sync_dedup_hours", "")
    }
    ui_config["sync_auto_purge"] = {
        "value": str(sync.get("auto_purge", True)).lower(),
        "description": descriptions.get("sync_auto_purge", "")
    }

    # RSS
    rss = config.get("rss", {})
    ui_config["rss_domain"] = {
        "value": rss.get("domain", "localhost:8000"),
        "description": descriptions.get("rss_domain", "")
    }
    ui_config["rss_scheme"] = {
        "value": rss.get("scheme", "http"),
        "description": descriptions.get("rss_scheme", "")
    }
    ui_config["rss_title"] = {
        "value": rss.get("title", "Grabb2RSS"),
        "description": descriptions.get("rss_title", "")
    }
    ui_config["rss_description"] = {
        "value": rss.get("description", "Prowlarr to RSS Feed"),
        "description": descriptions.get("rss_description", "")
    }

    return ui_config


def save_config_from_ui(ui_config: Dict[str, Any]) -> bool:
    """
    Sauvegarde la configuration depuis l'UI dans settings.yml
    ui_config est au format {key: {value: ..., description: ...}}
    """
    # Charger la config actuelle
    config = load_config()

    # Helper pour convertir les valeurs
    def get_value(key: str, default: Any = ""):
        if key in ui_config:
            if isinstance(ui_config[key], dict):
                return ui_config[key].get("value", default)
            return ui_config[key]
        return default

    def to_bool(value):
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() == "true"
        return False

    def to_int(value, default=0):
        try:
            return int(value) if value else default
        except:
            return default

    # Mettre à jour la config
    config["prowlarr"] = {
        "url": get_value("prowlarr_url"),
        "api_key": get_value("prowlarr_api_key"),
        "history_page_size": to_int(get_value("prowlarr_history_page_size"), 500)
    }

    config["radarr"] = {
        "url": get_value("radarr_url"),
        "api_key": get_value("radarr_api_key"),
        "enabled": to_bool(get_value("radarr_enabled"))
    }

    config["sonarr"] = {
        "url": get_value("sonarr_url"),
        "api_key": get_value("sonarr_api_key"),
        "enabled": to_bool(get_value("sonarr_enabled"))
    }

    config["sync"] = {
        "interval": to_int(get_value("sync_interval"), 3600),
        "retention_hours": to_int(get_value("sync_retention_hours"), 168),
        "dedup_hours": to_int(get_value("sync_dedup_hours"), 168),
        "auto_purge": to_bool(get_value("sync_auto_purge", "true"))
    }

    config["rss"] = {
        "domain": get_value("rss_domain", "localhost:8000"),
        "scheme": get_value("rss_scheme", "http"),
        "title": get_value("rss_title", "Grabb2RSS"),
        "description": get_value("rss_description", "Prowlarr to RSS Feed")
    }

    # Sauvegarder
    return save_config(config)
