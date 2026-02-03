# auth.py
"""
Module de gestion de l'authentification pour Grabb2RSS
- Authentification mono-utilisateur avec mot de passe hashé
- Gestion des sessions avec cookies sécurisés
- API Keys pour accès RSS externe
"""
import hashlib
import os
import logging
import secrets
import hmac
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from pathlib import Path
import yaml

# Chemins
CONFIG_FILE = Path("/config/settings.yml")
logger = logging.getLogger(__name__)

# Durée de validité des sessions (7 jours)
SESSION_DURATION = timedelta(days=7)

from db import get_db


def hash_password(password: str) -> str:
    """
    Hash un mot de passe avec SHA-256 + salt

    Args:
        password: Mot de passe en clair

    Returns:
        Hash au format: salt$hash
    """
    # Générer un salt aléatoire
    salt = secrets.token_hex(32)

    # Hasher le mot de passe avec le salt
    pwd_hash = hashlib.sha256(f"{salt}{password}".encode()).hexdigest()

    return f"{salt}${pwd_hash}"


def verify_password(password: str, password_hash: str) -> bool:
    """
    Vérifie un mot de passe contre son hash

    Args:
        password: Mot de passe en clair
        password_hash: Hash au format salt$hash

    Returns:
        True si le mot de passe est correct
    """
    try:
        salt, expected_hash = password_hash.split('$', 1)
        pwd_hash = hashlib.sha256(f"{salt}{password}".encode()).hexdigest()

        # Comparaison sécurisée contre timing attacks
        return hmac.compare_digest(pwd_hash, expected_hash)
    except (ValueError, AttributeError):
        return False


def get_auth_config() -> Dict[str, Any]:
    """
    Récupère la configuration d'authentification depuis settings.yml

    Returns:
        Dictionnaire avec la config auth ou None si pas configuré
    """
    if not CONFIG_FILE.exists():
        return None

    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
            return config.get("auth", {}) if config else {}
    except Exception as e:
        logger.warning("Erreur lecture config auth: %s", e)
        return {}


def _parse_bool(value: Any) -> bool:
    """Convertit une valeur en booléen de manière permissive."""
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def get_auth_cookie_secure() -> bool:
    """
    Détermine si le cookie de session doit être sécurisé (HTTPS only).
    Priorité: variable d'environnement AUTH_COOKIE_SECURE, puis settings.yml.
    """
    env_value = os.getenv("AUTH_COOKIE_SECURE")
    if env_value is not None:
        return _parse_bool(env_value)

    auth_config = get_auth_config() or {}
    return _parse_bool(auth_config.get("cookie_secure", False))


def save_auth_config(auth_config: Dict[str, Any]) -> bool:
    """
    Sauvegarde la configuration d'authentification dans settings.yml

    Args:
        auth_config: Dictionnaire avec la config auth

    Returns:
        True si succès, False sinon
    """
    try:
        # Charger la config complète
        config = {}
        if CONFIG_FILE.exists():
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f) or {}

        # Mettre à jour la section auth
        config["auth"] = auth_config

        # Sauvegarder
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            yaml.dump(config, f, default_flow_style=False, allow_unicode=True)

        logger.info("Configuration auth sauvegardée")
        return True
    except Exception as e:
        logger.error("Erreur sauvegarde config auth: %s", e)
        return False


def is_auth_enabled() -> bool:
    """
    Vérifie si l'authentification est activée

    Returns:
        True si l'authentification est activée
    """
    auth_config = get_auth_config()
    return auth_config and auth_config.get("enabled", False)


def verify_credentials(username: str, password: str) -> bool:
    """
    Vérifie les credentials d'un utilisateur

    Args:
        username: Nom d'utilisateur
        password: Mot de passe en clair

    Returns:
        True si les credentials sont valides
    """
    auth_config = get_auth_config()

    if not auth_config:
        return False

    # Vérifier le username
    if username != auth_config.get("username"):
        return False

    # Vérifier le password
    password_hash = auth_config.get("password_hash")
    if not password_hash:
        return False

    return verify_password(password, password_hash)


def create_session() -> str:
    """
    Crée une nouvelle session

    Returns:
        Token de session unique
    """
    # Générer un token sécurisé
    session_token = secrets.token_urlsafe(32)

    # Stocker la session en DB
    now = datetime.utcnow()
    expires_at = now + SESSION_DURATION
    with get_db() as conn:
        conn.execute(
            "INSERT INTO sessions (token, created_at, expires_at) VALUES (?, ?, ?)",
            (session_token, now.isoformat() + "Z", expires_at.isoformat() + "Z")
        )
        conn.commit()

    return session_token


def verify_session(session_token: Optional[str]) -> bool:
    """
    Vérifie la validité d'une session

    Args:
        session_token: Token de session

    Returns:
        True si la session est valide
    """
    if not session_token:
        return False

    with get_db() as conn:
        row = conn.execute(
            "SELECT expires_at FROM sessions WHERE token = ?",
            (session_token,)
        ).fetchone()
        if not row:
            return False

        expires_at = row[0]
        now = datetime.utcnow().isoformat() + "Z"
        if now > expires_at:
            conn.execute("DELETE FROM sessions WHERE token = ?", (session_token,))
            conn.commit()
            return False

    return True


def get_username_from_session(session_token: Optional[str]) -> Optional[str]:
    """
    Récupère le nom d'utilisateur depuis une session valide
    Comme le système est mono-utilisateur, on retourne le username de la config

    Args:
        session_token: Token de session

    Returns:
        Nom d'utilisateur si la session est valide, None sinon
    """
    if not verify_session(session_token):
        return None

    auth_config = get_auth_config()
    if not auth_config:
        return None

    return auth_config.get("username")


def delete_session(session_token: str) -> bool:
    """
    Supprime une session (logout)

    Args:
        session_token: Token de session

    Returns:
        True si la session a été supprimée
    """
    with get_db() as conn:
        cur = conn.execute("DELETE FROM sessions WHERE token = ?", (session_token,))
        conn.commit()
        return cur.rowcount > 0


def cleanup_expired_sessions():
    """
    Nettoie les sessions expirées (à appeler périodiquement)
    """
    now = datetime.utcnow().isoformat() + "Z"
    with get_db() as conn:
        cur = conn.execute("DELETE FROM sessions WHERE expires_at < ?", (now,))
        conn.commit()
        if cur.rowcount:
            logger.info("%s session(s) expirée(s) nettoyée(s)", cur.rowcount)


def generate_api_key() -> str:
    """
    Génère une nouvelle API key

    Returns:
        API key unique au format: grabb2rss_xxxxxx
    """
    key = secrets.token_urlsafe(32)
    return f"grabb2rss_{key}"


def get_api_keys() -> list:
    """
    Récupère toutes les API keys configurées

    Returns:
        Liste des API keys avec leurs metadata
    """
    auth_config = get_auth_config()
    if not auth_config:
        return []

    return auth_config.get("api_keys", [])


def verify_api_key(api_key: str) -> bool:
    """
    Vérifie la validité d'une API key

    Args:
        api_key: API key à vérifier

    Returns:
        True si l'API key est valide
    """
    if not api_key:
        return False

    api_keys = get_api_keys()

    # Chercher l'API key
    for key_data in api_keys:
        if key_data.get("key") == api_key:
            # Vérifier si elle est active
            return key_data.get("enabled", True)

    return False


def create_api_key(name: str, enabled: bool = True) -> Optional[Dict[str, Any]]:
    """
    Crée une nouvelle API key

    Args:
        name: Nom descriptif de l'API key
        enabled: Si l'API key est activée

    Returns:
        Dictionnaire avec les données de l'API key ou None si erreur
    """
    auth_config = get_auth_config()
    if not auth_config:
        auth_config = {}

    # Générer la clé
    api_key = generate_api_key()

    # Créer l'entrée
    key_data = {
        "key": api_key,
        "name": name,
        "enabled": enabled,
        "created_at": datetime.now().isoformat()
    }

    # Ajouter à la liste
    api_keys = auth_config.get("api_keys", [])
    api_keys.append(key_data)
    auth_config["api_keys"] = api_keys

    # Sauvegarder
    if save_auth_config(auth_config):
        return key_data

    return None


def delete_api_key(api_key: str) -> bool:
    """
    Supprime une API key

    Args:
        api_key: API key à supprimer

    Returns:
        True si l'API key a été supprimée
    """
    auth_config = get_auth_config()
    if not auth_config:
        return False

    api_keys = auth_config.get("api_keys", [])

    # Filtrer pour supprimer la clé
    new_keys = [k for k in api_keys if k.get("key") != api_key]

    if len(new_keys) == len(api_keys):
        # Aucune clé supprimée
        return False

    auth_config["api_keys"] = new_keys
    return save_auth_config(auth_config)


def toggle_api_key(api_key: str, enabled: bool) -> bool:
    """
    Active/désactive une API key

    Args:
        api_key: API key à modifier
        enabled: Nouvel état

    Returns:
        True si l'API key a été modifiée
    """
    auth_config = get_auth_config()
    if not auth_config:
        return False

    api_keys = auth_config.get("api_keys", [])

    # Chercher et modifier
    modified = False
    for key_data in api_keys:
        if key_data.get("key") == api_key:
            key_data["enabled"] = enabled
            modified = True
            break

    if not modified:
        return False

    auth_config["api_keys"] = api_keys
    return save_auth_config(auth_config)


def is_local_request(client_host: Optional[str]) -> bool:
    """
    Détermine si une requête provient du réseau local

    Args:
        client_host: IP du client

    Returns:
        True si la requête est locale
    """
    if not client_host:
        return False

    # IPs locales
    local_ips = [
        '127.0.0.1',
        'localhost',
        '::1',
        '0.0.0.0'
    ]

    # Vérifier si c'est une IP locale
    if client_host in local_ips:
        return True

    # Vérifier les réseaux privés (172.x.x.x, 192.168.x.x, 10.x.x.x)
    if client_host.startswith('172.') or client_host.startswith('192.168.') or client_host.startswith('10.'):
        return True

    return False


def setup_initial_auth(username: str, password: str) -> bool:
    """
    Configure l'authentification initiale lors du setup

    Args:
        username: Nom d'utilisateur
        password: Mot de passe en clair

    Returns:
        True si succès
    """
    # Hasher le mot de passe
    password_hash = hash_password(password)

    # Créer la config auth
    auth_config = {
        "enabled": True,
        "username": username,
        "password_hash": password_hash,
        "api_keys": []
    }

    return save_auth_config(auth_config)


def change_password(old_password: str, new_password: str) -> bool:
    """
    Change le mot de passe de l'utilisateur

    Args:
        old_password: Ancien mot de passe
        new_password: Nouveau mot de passe

    Returns:
        True si succès
    """
    auth_config = get_auth_config()
    if not auth_config:
        return False

    # Vérifier l'ancien mot de passe
    username = auth_config.get("username")
    if not verify_credentials(username, old_password):
        return False

    # Hasher le nouveau mot de passe
    password_hash = hash_password(new_password)

    # Mettre à jour
    auth_config["password_hash"] = password_hash

    return save_auth_config(auth_config)
