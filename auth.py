# auth.py
"""
Module d'authentification pour Grabb2RSS
- Authentification mono-utilisateur par session (interface web)
- Authentification par API Key (flux RSS externe)
- Accès local sans authentification (flux RSS depuis le réseau Docker)
"""

from datetime import datetime, timedelta
from typing import Optional
from passlib.context import CryptContext
from jose import JWTError, jwt
import secrets
from pathlib import Path

# Configuration de l'authentification
SECRET_KEY = secrets.token_urlsafe(32)  # Généré au démarrage
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 heures

# Contexte pour le hashing des mots de passe
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Vérifie un mot de passe contre son hash"""
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except Exception:
        return False


def get_password_hash(password: str) -> str:
    """Hash un mot de passe"""
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Créé un token JWT"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def verify_token(token: str) -> Optional[dict]:
    """Vérifie un token JWT et retourne les données"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None


def generate_api_key() -> str:
    """Génère une nouvelle API key sécurisée"""
    return secrets.token_urlsafe(32)


def verify_api_key(provided_key: str, stored_key: str) -> bool:
    """Vérifie une API key"""
    return secrets.compare_digest(provided_key, stored_key)


def is_local_request(request_host: Optional[str], client_host: Optional[str] = None) -> bool:
    """
    Détermine si la requête provient du réseau local/Docker

    Args:
        request_host: Host header de la requête
        client_host: IP du client

    Returns:
        True si la requête est locale, False sinon
    """
    if not request_host and not client_host:
        return False

    # Indicateurs d'accès local
    local_indicators = [
        'localhost',
        '127.0.0.1',
        '::1',
        '0.0.0.0',
        'grabb2rss',
        'grab2rss',
    ]

    # Vérifier le host header
    if request_host:
        host_lower = request_host.lower()
        if any(indicator in host_lower for indicator in local_indicators):
            return True
        # Vérifier les réseaux privés dans le host
        if host_lower.startswith('10.') or host_lower.startswith('192.168.') or host_lower.startswith('172.'):
            return True

    # Vérifier l'IP du client
    if client_host:
        client_lower = client_host.lower()
        if any(indicator in client_lower for indicator in local_indicators):
            return True
        # Vérifier les réseaux privés
        if client_lower.startswith('10.') or client_lower.startswith('192.168.') or client_lower.startswith('172.'):
            return True

    return False


class AuthConfig:
    """Configuration d'authentification chargée depuis settings.yml"""

    def __init__(self):
        self.enabled = False
        self.username = ""
        self.password_hash = ""
        self.api_key = ""
        self.require_auth_for_rss = True  # Si False, RSS accessible sans auth

    def load_from_yaml(self, yaml_config: dict):
        """Charge la config d'auth depuis le YAML"""
        auth = yaml_config.get("auth", {})
        self.enabled = auth.get("enabled", False)
        self.username = auth.get("username", "")
        self.password_hash = auth.get("password_hash", "")
        self.api_key = auth.get("api_key", "")
        self.require_auth_for_rss = auth.get("require_auth_for_rss", True)

    def authenticate_user(self, username: str, password: str) -> bool:
        """Authentifie un utilisateur avec username/password"""
        if not self.enabled:
            return True  # Si auth désactivée, tout le monde passe

        if username != self.username:
            return False

        return verify_password(password, self.password_hash)

    def verify_api_key(self, api_key: str) -> bool:
        """Vérifie une API key"""
        if not self.enabled:
            return True

        if not self.api_key:
            return False

        return verify_api_key(api_key, self.api_key)


# Instance globale de la configuration d'auth
auth_config = AuthConfig()
