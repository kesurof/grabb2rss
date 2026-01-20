# setup.py
"""
Module de configuration initiale pour Grab2RSS
Gère le setup wizard au premier lancement
"""
import yaml
from pathlib import Path
from typing import Optional, Dict, Any

# Chemin du fichier de configuration
CONFIG_FILE = Path("/config/settings.yml")
CONFIG_DIR = Path("/config")

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
        "enabled": False
    },
    "sonarr": {
        "url": "",
        "api_key": "",
        "enabled": False
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
        "title": "Grab2RSS",
        "description": "Prowlarr to RSS Feed"
    },
    "app": {
        "host": "0.0.0.0",
        "port": 8000
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
        print(f"⚠️  Erreur lecture config: {e}")
        return DEFAULT_CONFIG.copy()


def save_config(config: Dict[str, Any]) -> bool:
    """Sauvegarde la configuration dans le fichier YAML"""
    try:
        # Créer le répertoire si nécessaire
        print(f"📁 Création du répertoire: {CONFIG_DIR}")
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)

        # Vérifier les permissions
        import os
        if CONFIG_DIR.exists():
            print(f"✅ Répertoire existe: {CONFIG_DIR}")
            print(f"   Permissions: {oct(os.stat(CONFIG_DIR).st_mode)[-3:]}")
            print(f"   User ID: {os.getuid()}, Group ID: {os.getgid()}")

        print(f"💾 Sauvegarde dans: {CONFIG_FILE}")
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            yaml.dump(config, f, default_flow_style=False, allow_unicode=True)

        print(f"✅ Configuration sauvegardée: {CONFIG_FILE}")
        return True
    except PermissionError as e:
        print(f"❌ Erreur de permissions: {e}")
        print(f"   Vérifiez que l'utilisateur a les droits d'écriture sur {CONFIG_DIR}")
        return False
    except Exception as e:
        print(f"❌ Erreur sauvegarde config: {e}")
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
        import requests
        response = requests.get(
            f"{url}/api/v1/health",
            headers={"X-Api-Key": api_key},
            timeout=5
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
        return False, f"Erreur: {str(e)}"


def create_initial_config_if_needed():
    """Crée un fichier de config initial si nécessaire"""
    if not CONFIG_FILE.exists():
        print("📝 Création de la configuration initiale...")
        save_config(DEFAULT_CONFIG)
