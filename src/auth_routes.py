# auth_routes.py
"""
Routes d'authentification pour Grabb2RSS
"""
from fastapi import APIRouter, HTTPException, Request, Response, Cookie
from typing import Optional
import time
import logging

from models import (
    LoginRequest, LoginResponse, AuthStatus, PasswordChangeRequest,
    ApiKeyCreate, ApiKeyResponse
)
from auth import (
    is_auth_enabled, verify_credentials, create_session, verify_session,
    delete_session, get_api_keys, create_api_key, delete_api_key,
    toggle_api_key, change_password, get_auth_config, cleanup_expired_sessions,
    get_auth_cookie_secure
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["authentication"])

LOGIN_RATE_LIMIT_MAX_ATTEMPTS = 5
LOGIN_RATE_LIMIT_WINDOW_SECONDS = 10 * 60
LOGIN_RATE_LIMIT_BLOCK_SECONDS = 15 * 60
_login_attempts: dict[str, dict[str, int | float]] = {}


def _get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _is_rate_limited(client_ip: str) -> tuple[bool, int]:
    now = time.time()
    entry = _login_attempts.get(client_ip)
    if not entry:
        return False, 0
    if entry["blocked_until"] > now:
        return True, int(entry["blocked_until"] - now)
    if now - entry["window_start"] > LOGIN_RATE_LIMIT_WINDOW_SECONDS:
        _login_attempts.pop(client_ip, None)
        return False, 0
    return False, 0


def _register_failed_attempt(client_ip: str) -> None:
    now = time.time()
    entry = _login_attempts.get(client_ip)
    if not entry or now - entry["window_start"] > LOGIN_RATE_LIMIT_WINDOW_SECONDS:
        _login_attempts[client_ip] = {
            "window_start": now,
            "count": 1,
            "blocked_until": 0,
        }
        return

    entry["count"] += 1
    if entry["count"] >= LOGIN_RATE_LIMIT_MAX_ATTEMPTS:
        entry["blocked_until"] = now + LOGIN_RATE_LIMIT_BLOCK_SECONDS


def _reset_attempts(client_ip: str) -> None:
    _login_attempts.pop(client_ip, None)


@router.post("/login", response_model=LoginResponse)
async def login(request: Request, response: Response):
    """
    Authentification de l'utilisateur

    Args:
        request: Credentials (username, password)
        response: Response pour définir le cookie

    Returns:
        LoginResponse avec le résultat de l'authentification
    """
    # Vérifier si l'auth est activée
    if not is_auth_enabled():
        raise HTTPException(status_code=400, detail="L'authentification n'est pas activée")

    client_ip = _get_client_ip(request)
    is_limited, retry_after = _is_rate_limited(client_ip)
    if is_limited:
        logger.warning("Rate limit login pour IP %s (%ss)", client_ip, retry_after)
        raise HTTPException(
            status_code=429,
            detail=f"Trop de tentatives. Réessayez dans {retry_after}s"
        )

    # Support JSON + form-urlencoded (fallback sans JS)
    try:
        content_type = request.headers.get("content-type", "")
        if content_type.startswith("application/json"):
            payload = await request.json()
        else:
            form = await request.form()
            payload = {"username": form.get("username", ""), "password": form.get("password", "")}
        login_request = LoginRequest(**payload)
    except Exception:
        raise HTTPException(status_code=400, detail="Requête de login invalide")

    # Vérifier les credentials
    if not verify_credentials(login_request.username, login_request.password):
        _register_failed_attempt(client_ip)
        logger.warning("Échec login pour %s depuis %s", login_request.username, client_ip)
        return LoginResponse(
            success=False,
            message="Identifiants incorrects"
        )

    _reset_attempts(client_ip)

    # Créer une session
    session_token = create_session()

    # Définir le cookie de session
    cookie_secure = get_auth_cookie_secure()
    response.set_cookie(
        key="session_token",
        value=session_token,
        httponly=True,
        secure=cookie_secure,
        samesite="lax",
        max_age=7 * 24 * 3600  # 7 jours
    )

    logger.info("Connexion réussie pour %s", login_request.username)

    return LoginResponse(
        success=True,
        message="Connexion réussie",
        session_token=session_token
    )


@router.post("/logout")
async def logout(
    response: Response,
    session_token: Optional[str] = Cookie(None)
):
    """
    Déconnexion de l'utilisateur

    Args:
        response: Response pour supprimer le cookie
        session_token: Token de session depuis le cookie

    Returns:
        Message de confirmation
    """
    if session_token:
        delete_session(session_token)

    # Supprimer le cookie
    cookie_secure = get_auth_cookie_secure()
    response.delete_cookie(
        key="session_token",
        httponly=True,
        secure=cookie_secure,
        samesite="lax"
    )

    logger.info("✅ Déconnexion réussie")

    return {"success": True, "message": "Déconnexion réussie"}


@router.get("/status", response_model=AuthStatus)
async def auth_status(
    session_token: Optional[str] = Cookie(None)
):
    """
    Récupère le statut d'authentification de l'utilisateur

    Args:
        session_token: Token de session depuis le cookie

    Returns:
        AuthStatus avec les informations d'authentification
    """
    # Nettoyer les sessions expirées
    cleanup_expired_sessions()

    # Vérifier si l'auth est activée
    enabled = is_auth_enabled()

    if not enabled:
        return AuthStatus(
            authenticated=True,  # Pas d'auth = accès libre
            enabled=False
        )

    # Vérifier la session
    authenticated = verify_session(session_token)

    # Récupérer le username si authentifié
    username = None
    if authenticated:
        auth_config = get_auth_config()
        username = auth_config.get("username")

    return AuthStatus(
        authenticated=authenticated,
        enabled=enabled,
        username=username
    )


@router.post("/change-password")
async def change_password_route(
    request: PasswordChangeRequest,
    session_token: Optional[str] = Cookie(None)
):
    """
    Change le mot de passe de l'utilisateur

    Args:
        request: Ancien et nouveau mot de passe
        session_token: Token de session

    Returns:
        Message de confirmation
    """
    # Vérifier la session
    if not verify_session(session_token):
        raise HTTPException(status_code=401, detail="Non authentifié")

    # Changer le mot de passe
    success = change_password(request.old_password, request.new_password)

    if not success:
        raise HTTPException(status_code=400, detail="Ancien mot de passe incorrect")

    logger.info("✅ Mot de passe changé avec succès")

    return {"success": True, "message": "Mot de passe changé avec succès"}


# ==================== API KEYS ====================

@router.get("/api-keys")
async def list_api_keys(
    session_token: Optional[str] = Cookie(None)
):
    """
    Liste toutes les API keys

    Args:
        session_token: Token de session

    Returns:
        Liste des API keys
    """
    # Vérifier la session
    if not verify_session(session_token):
        raise HTTPException(status_code=401, detail="Non authentifié")

    api_keys = get_api_keys()

    # Masquer une partie de la clé pour la sécurité
    for key in api_keys:
        key_value = key.get("key", "")
        if len(key_value) > 20:
            key["key_masked"] = key_value[:15] + "..." + key_value[-5:]
        else:
            key["key_masked"] = key_value

    return {"api_keys": api_keys}


@router.post("/api-keys", response_model=ApiKeyResponse)
async def create_api_key_route(
    request: ApiKeyCreate,
    session_token: Optional[str] = Cookie(None)
):
    """
    Crée une nouvelle API key

    Args:
        request: Nom et état de l'API key
        session_token: Token de session

    Returns:
        Données de l'API key créée
    """
    # Vérifier la session
    if not verify_session(session_token):
        raise HTTPException(status_code=401, detail="Non authentifié")

    # Créer l'API key
    key_data = create_api_key(request.name, request.enabled)

    if not key_data:
        raise HTTPException(status_code=500, detail="Erreur lors de la création de l'API key")

    logger.info(f"✅ API key créée: {request.name}")

    return ApiKeyResponse(
        key=key_data["key"],
        name=key_data["name"],
        enabled=key_data["enabled"],
        created_at=key_data["created_at"]
    )


@router.delete("/api-keys/{api_key}")
async def delete_api_key_route(
    api_key: str,
    session_token: Optional[str] = Cookie(None)
):
    """
    Supprime une API key

    Args:
        api_key: API key à supprimer
        session_token: Token de session

    Returns:
        Message de confirmation
    """
    # Vérifier la session
    if not verify_session(session_token):
        raise HTTPException(status_code=401, detail="Non authentifié")

    # Supprimer l'API key
    success = delete_api_key(api_key)

    if not success:
        raise HTTPException(status_code=404, detail="API key non trouvée")

    logger.info(f"✅ API key supprimée: {api_key[:15]}...")

    return {"success": True, "message": "API key supprimée"}


@router.patch("/api-keys/{api_key}")
async def toggle_api_key_route(
    api_key: str,
    enabled: bool,
    session_token: Optional[str] = Cookie(None)
):
    """
    Active/désactive une API key

    Args:
        api_key: API key à modifier
        enabled: Nouvel état
        session_token: Token de session

    Returns:
        Message de confirmation
    """
    # Vérifier la session
    if not verify_session(session_token):
        raise HTTPException(status_code=401, detail="Non authentifié")

    # Modifier l'API key
    success = toggle_api_key(api_key, enabled)

    if not success:
        raise HTTPException(status_code=404, detail="API key non trouvée")

    status = "activée" if enabled else "désactivée"
    logger.info(f"✅ API key {status}: {api_key[:15]}...")

    return {"success": True, "message": f"API key {status}"}
