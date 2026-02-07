# setup.py
"""
Module de configuration initiale pour Grabb2RSS
Gère le setup wizard au premier lancement
"""
import yaml
import logging
from typing import Optional, Dict, Any
import requests

# Chemin du fichier de configuration
from paths import SETTINGS_FILE, CONFIG_DIR
CONFIG_FILE = SETTINGS_FILE
logger = logging.getLogger(__name__)

# Configuration par défaut
DEFAULT_CONFIG = {
    "prowlarr": {
        "url": "",
        "api_key": ""
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
        "auto_purge": True,
        "retention_hours": 168
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
    "webhook": {
        "enabled": False,
        "token": "",
        "min_score": 3,
        "strict": True,
        "download": True
    },
    "history": {
        "sync_interval_seconds": 7200,
        "lookback_days": 7,
        "download_from_history": True,
        "min_score": 3,
        "strict_hash": False,
        "ingestion_mode": "webhook_plus_history"
    },
    "history_apps": [],
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
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            yaml.dump(config, f, default_flow_style=False, allow_unicode=True)
        logger.info("Configuration sauvegardée: %s", CONFIG_FILE)
        return True
    except PermissionError as e:
        logger.error("Erreur de permissions: %s", e)
        return False
    except Exception as e:
        logger.error("Erreur sauvegarde config: %s", e)
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


def get_history_apps() -> list[dict]:
    """Retourne la liste normalisée des instances history consolidé depuis settings.yml."""
    config = load_config()
    apps = config.get("history_apps", [])
    if not isinstance(apps, list):
        return []

    normalized: list[dict] = []
    for app in apps:
        if not isinstance(app, dict):
            continue
        name = (app.get("name") or "").strip()
        url = (app.get("url") or "").strip()
        api_key = (app.get("api_key") or "").strip()
        app_type = (app.get("type") or name).strip().lower()
        enabled = bool(app.get("enabled", True))
        if not (name and url and api_key):
            continue
        normalized.append({
            "name": name.lower(),
            "url": url.rstrip("/"),
            "api_key": api_key,
            "type": app_type,
            "enabled": enabled,
        })
    return normalized


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
        "radarr_url": "URL de Radarr (ex: http://radarr:7878)",
        "radarr_api_key": "Clé API Radarr",
        "radarr_enabled": "Activer l'intégration Radarr (true/false)",
        "sonarr_url": "URL de Sonarr (ex: http://sonarr:8989)",
        "sonarr_api_key": "Clé API Sonarr",
        "sonarr_enabled": "Activer l'intégration Sonarr (true/false)",
        "sync_retention_hours": "Nombre d'heures avant suppression automatique (168 = 7j, 0 = infini)",
        "sync_auto_purge": "Activer la suppression automatique des anciens grabs (true/false)",
        "rss_domain": "Domaine pour les URLs RSS (ex: grabb2rss.example.com)",
        "rss_scheme": "Protocole pour les URLs RSS (http ou https)",
        "rss_title": "Titre du flux RSS",
        "rss_description": "Description du flux RSS",
        "rss_allowed_hosts": "Liste blanche d'hôtes RSS (séparés par virgules, optionnel)"
        ,
        "webhook_enabled": "Activer le webhook Grab (recommandé)",
        "webhook_token": "Token de sécurité pour le webhook",
        "webhook_min_score": "Score minimum de matching (3 recommandé)",
        "webhook_strict": "Refuser si matching insuffisant ou hash invalide",
        "webhook_download": "Télécharger le .torrent via Prowlarr",
        "history_sync_interval_seconds": "Intervalle de sync history en secondes (ex: 7200 = 2h)",
        "history_lookback_days": "Fenêtre de rattrapage history en jours (ex: 7)",
        "history_download_from_history": "Télécharger les .torrents pendant la sync history",
        "history_min_score": "Score minimum de matching en sync history",
        "history_strict_hash": "Refuser si hash invalide pendant la sync history",
        "history_ingestion_mode": "Mode d'ingestion: webhook_only | webhook_plus_history | history_only",
        "history_apps": "Instances Radarr/Sonarr pour l'historique consolidé (JSON)"
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
    ui_config["sync_retention_hours"] = {
        "value": str(sync.get("retention_hours", 168)),
        "description": descriptions.get("sync_retention_hours", "")
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
    allowed_hosts = rss.get("allowed_hosts", [])
    if isinstance(allowed_hosts, list):
        allowed_hosts_value = ", ".join([str(v) for v in allowed_hosts if str(v).strip()])
    else:
        allowed_hosts_value = str(allowed_hosts or "")
    ui_config["rss_allowed_hosts"] = {
        "value": allowed_hosts_value,
        "description": descriptions.get("rss_allowed_hosts", "")
    }

    # Webhook
    webhook = config.get("webhook", {})
    ui_config["webhook_enabled"] = {
        "value": str(webhook.get("enabled", False)).lower(),
        "description": descriptions.get("webhook_enabled", "")
    }
    ui_config["webhook_token"] = {
        "value": webhook.get("token", ""),
        "description": descriptions.get("webhook_token", "")
    }
    ui_config["webhook_min_score"] = {
        "value": str(webhook.get("min_score", 3)),
        "description": descriptions.get("webhook_min_score", "")
    }
    ui_config["webhook_strict"] = {
        "value": str(webhook.get("strict", True)).lower(),
        "description": descriptions.get("webhook_strict", "")
    }
    ui_config["webhook_download"] = {
        "value": str(webhook.get("download", True)).lower(),
        "description": descriptions.get("webhook_download", "")
    }

    # Auth
    auth = config.get("auth", {})
    ui_config["auth_enabled"] = {
        "value": str(auth.get("enabled", False)).lower(),
        "description": descriptions.get("auth_enabled", "")
    }
    ui_config["auth_cookie_secure"] = {
        "value": str(auth.get("cookie_secure", False)).lower(),
        "description": descriptions.get("auth_cookie_secure", "")
    }

    history_apps = config.get("history_apps", [])
    try:
        history_value = json.dumps(history_apps, ensure_ascii=False, indent=2)
    except Exception:
        history_value = "[]"
    history_cfg = config.get("history", {})
    ui_config["history_sync_interval_seconds"] = {
        "value": str(history_cfg.get("sync_interval_seconds", 7200)),
        "description": descriptions.get("history_sync_interval_seconds", "")
    }
    ui_config["history_lookback_days"] = {
        "value": str(history_cfg.get("lookback_days", 7)),
        "description": descriptions.get("history_lookback_days", "")
    }
    ui_config["history_download_from_history"] = {
        "value": str(history_cfg.get("download_from_history", True)).lower(),
        "description": descriptions.get("history_download_from_history", "")
    }
    ui_config["history_min_score"] = {
        "value": str(history_cfg.get("min_score", 3)),
        "description": descriptions.get("history_min_score", "")
    }
    ui_config["history_strict_hash"] = {
        "value": str(history_cfg.get("strict_hash", False)).lower(),
        "description": descriptions.get("history_strict_hash", "")
    }
    ui_config["history_ingestion_mode"] = {
        "value": str(history_cfg.get("ingestion_mode", "webhook_plus_history")),
        "description": descriptions.get("history_ingestion_mode", "")
    }
    ui_config["history_apps"] = {
        "value": history_value,
        "description": descriptions.get("history_apps", "")
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

    def to_list(value) -> list[str]:
        if isinstance(value, list):
            return [str(v).strip() for v in value if str(v).strip()]
        if isinstance(value, str):
            return [v.strip() for v in value.split(",") if v.strip()]
        return []

    # Mettre à jour la config
    config["prowlarr"] = {
        "url": get_value("prowlarr_url"),
        "api_key": get_value("prowlarr_api_key")
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
        "retention_hours": to_int(get_value("sync_retention_hours"), 168),
        "auto_purge": to_bool(get_value("sync_auto_purge", "true"))
    }

    config["rss"] = {
        "domain": get_value("rss_domain", "localhost:8000"),
        "scheme": get_value("rss_scheme", "http"),
        "title": get_value("rss_title", "Grabb2RSS"),
        "description": get_value("rss_description", "Prowlarr to RSS Feed"),
        "allowed_hosts": to_list(get_value("rss_allowed_hosts", ""))
    }

    config["webhook"] = {
        "enabled": to_bool(get_value("webhook_enabled", "false")),
        "token": get_value("webhook_token", ""),
        "min_score": to_int(get_value("webhook_min_score", 3), 3),
        "strict": to_bool(get_value("webhook_strict", "true")),
        "download": to_bool(get_value("webhook_download", "true"))
    }
    config["history"] = {
        "sync_interval_seconds": max(300, to_int(get_value("history_sync_interval_seconds", 7200), 7200)),
        "lookback_days": max(1, to_int(get_value("history_lookback_days", 7), 7)),
        "download_from_history": to_bool(get_value("history_download_from_history", "true")),
        "min_score": max(0, min(10, to_int(get_value("history_min_score", 3), 3))),
        "strict_hash": to_bool(get_value("history_strict_hash", "false")),
        "ingestion_mode": str(get_value("history_ingestion_mode", "webhook_plus_history") or "webhook_plus_history").strip().lower()
    }

    history_raw = get_value("history_apps", "[]")
    history_apps = []
    if isinstance(history_raw, list):
        history_apps = history_raw
    elif isinstance(history_raw, str):
        try:
            parsed = json.loads(history_raw)
            if isinstance(parsed, list):
                history_apps = parsed
        except Exception:
            history_apps = config.get("history_apps", [])

    # Radarr/Sonarr obligatoires pour l'historique consolidé
    if not config["radarr"].get("url") or not config["radarr"].get("api_key"):
        logger.error("Radarr obligatoire pour l'historique consolidé (url + api_key)")
        return False
    if not config["sonarr"].get("url") or not config["sonarr"].get("api_key"):
        logger.error("Sonarr obligatoire pour l'historique consolidé (url + api_key)")
        return False

    def _upsert_history(apps: list, name: str, url: str, api_key: str, app_type: str) -> list:
        filtered = [a for a in apps if not (isinstance(a, dict) and a.get("name") == name)]
        filtered.insert(0, {
            "name": name,
            "url": url,
            "api_key": api_key,
            "type": app_type,
            "enabled": True
        })
        return filtered

    history_apps = _upsert_history(
        history_apps,
        "radarr",
        config["radarr"].get("url"),
        config["radarr"].get("api_key"),
        "radarr"
    )
    history_apps = _upsert_history(
        history_apps,
        "sonarr",
        config["sonarr"].get("url"),
        config["sonarr"].get("api_key"),
        "sonarr"
    )

    config["history_apps"] = history_apps

    # Auth (préserver username/password_hash/api_keys existants)
    auth_cfg = config.get("auth", {}) if isinstance(config.get("auth"), dict) else {}
    auth_cfg["enabled"] = to_bool(get_value("auth_enabled", str(auth_cfg.get("enabled", False)).lower()))
    auth_cfg["cookie_secure"] = to_bool(get_value("auth_cookie_secure", str(auth_cfg.get("cookie_secure", False)).lower()))
    config["auth"] = auth_cfg

    # Sauvegarder
    return save_config(config)
