# api.py
from fastapi import FastAPI, HTTPException, Query, Request, Cookie
from fastapi.responses import Response, HTMLResponse, JSONResponse, RedirectResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
import logging
import psutil
import time
from datetime import datetime
from typing import Optional
import re
from urllib.parse import quote

from logging_config import setup_logging
from version import APP_VERSION
from config import (
    TORRENT_DIR, DB_PATH, DESCRIPTIONS, PROWLARR_URL, PROWLARR_API_KEY,
    CORS_ALLOW_ORIGINS, TORRENTS_EXPOSE_STATIC, WEBHOOK_ENABLED, WEBHOOK_TOKEN,
    WEBHOOK_MIN_SCORE, WEBHOOK_STRICT, WEBHOOK_DOWNLOAD,
    HISTORY_LOOKBACK_DAYS, HISTORY_DOWNLOAD_FROM_HISTORY, HISTORY_MIN_SCORE,
    HISTORY_STRICT_HASH, HISTORY_INGESTION_MODE
)
from db import (
    init_db, get_grabs, get_stats, purge_all, purge_by_retention,
    get_config, set_config, get_all_config, get_sync_logs, get_trackers, get_db,
    vacuum_database, get_db_stats, get_torrent_files_with_info, cleanup_orphan_torrents,
    delete_torrent_file, purge_all_torrents, delete_log, purge_all_logs, purge_all_db, resolve_torrent_path,
    get_grab_history_list, get_grab_history_record
)
from rss import generate_rss, generate_torrent_json
from models import GrabOut, GrabStats, SyncStatus
from scheduler import start_scheduler, stop_scheduler, get_sync_status, trigger_sync
import setup
from setup_routes import router as setup_router
from auth_routes import router as auth_router
from auth import is_auth_enabled, verify_session, verify_api_key, is_local_request, get_username_from_session
from auth import get_auth_config, save_auth_config, hash_password, create_session, get_auth_cookie_secure
from webhook_grab import handle_webhook_grab, generate_webhook_token, recover_from_history
from history_reconcile import sync_grab_history

setup_logging()
logger = logging.getLogger(__name__)

# Variable pour tracker le temps de démarrage
start_time = time.time()

app = FastAPI(
    title="Grab2RSS API",
    description="API pour Grab2RSS - Convert Prowlarr grabs en RSS",
    version=APP_VERSION
)

# Configuration des templates et fichiers statiques
# Utiliser un chemin absolu pour éviter les problèmes de résolution de chemin
from paths import TEMPLATES_DIR, STATIC_DIR, SETTINGS_FILE

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


@app.middleware("http")
async def add_version_header(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-App-Version"] = APP_VERSION
    return response

# Middleware d'authentification simplifié
class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Si auth désactivée, tout est public
        if not is_auth_enabled():
            if not setup.is_first_run():
                admin_blocked_routes = {
                    ("POST", "/api/config"),
                    ("POST", "/api/setup/save"),
                    ("POST", "/api/purge/all"),
                    ("POST", "/api/purge/retention"),
                    ("POST", "/api/sync/trigger"),
                    ("POST", "/api/cache/clear"),
                    ("POST", "/api/db/vacuum"),
                    ("POST", "/api/torrents/purge-all"),
                    ("POST", "/api/logs/purge-all"),
                    ("POST", "/api/db/purge-all"),
                    ("POST", "/api/history/reconcile/sync"),
                    ("POST", "/api/auth/keys/generate"),
                    ("POST", "/api/auth/configure"),
                    ("DELETE", "/api/auth/keys/{key}"),
                }
                current_route = (request.method, request.url.path)
                is_admin_route = current_route in admin_blocked_routes
                if not is_admin_route and request.method == "DELETE" and request.url.path.startswith("/api/auth/keys/"):
                    is_admin_route = True
                if is_admin_route:
                    client_host = request.client.host if request.client else None
                    if not is_local_request(client_host):
                        raise HTTPException(
                            status_code=403,
                            detail="Action admin désactivée quand l'auth est inactive"
                        )
            return await call_next(request)

        # Routes toujours publiques même si auth activée
        public_routes = [
            '/health',              # Healthcheck pour Docker/K8s
            '/login',               # Page de login
            '/api/auth/login',      # API login
            '/api/auth/status',     # Statut auth
            '/api/webhook/grab',    # Webhook Grab (protégé par token)
        ]

        # Vérifier si route publique
        for route in public_routes:
            if request.url.path.startswith(route):
                return await call_next(request)

        # Ressources statiques toujours publiques
        if request.url.path.startswith('/static'):
            return await call_next(request)

        # Routes de setup : publiques SEULEMENT si setup non complété
        if request.url.path.startswith('/setup') or request.url.path.startswith('/api/setup'):
            if setup.is_first_run():
                return await call_next(request)
            # Sinon, continuer la vérification auth normale

        # Routes RSS : API key OBLIGATOIRE (même en local)
        # Exclure l'UI RSS (page HTML)
        if (request.url.path.startswith('/rss') and not request.url.path.startswith('/rss-ui')) or request.url.path.startswith('/feed'):
            # Si auth désactivée, accès libre aux RSS
            if not is_auth_enabled():
                return await call_next(request)

            # Vérifier l'API key via headers uniquement
            auth_header = request.headers.get('Authorization')
            api_key = None
            if auth_header:
                parts = auth_header.split()
                if len(parts) == 2 and parts[0].lower() == "bearer":
                    api_key = parts[1]

            if not api_key:
                api_key = request.headers.get('X-API-Key')
            if not api_key:
                api_key = request.query_params.get('apikey')

            if api_key and verify_api_key(api_key):
                return await call_next(request)

            # Pas d'API key valide : erreur 401
            raise HTTPException(
                status_code=401,
                detail="API key requise. Obtenez votre clé depuis le dashboard."
            )

        # Toutes les autres routes : vérifier session
        session_token = request.cookies.get('session_token')
        if not verify_session(session_token):
            # Rediriger vers login pour les pages HTML
            # Retourner 401 pour les API
            if request.url.path.startswith('/api'):
                raise HTTPException(status_code=401, detail="Non authentifié")
            else:
                # Pages HTML non authentifiées : rediriger vers login
                from fastapi.responses import RedirectResponse
                return RedirectResponse(url='/login', status_code=302)

        return await call_next(request)


# SetupRedirectMiddleware SUPPRIMÉ
# La logique de redirection vers /setup est maintenant gérée côté frontend via window.INITIAL_STATE
# pour être compatible avec oauth2-proxy (pas de redirections serveur HTTP 302)

# Inclure les routes AVANT les middlewares pour qu'ils soient bien pris en compte
app.include_router(setup_router)
app.include_router(auth_router)

# Monter les fichiers statiques
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
if TORRENTS_EXPOSE_STATIC and TORRENT_DIR.exists():
    app.mount("/torrents", StaticFiles(directory=str(TORRENT_DIR)), name="torrents")

# Ajouter les middlewares
# IMPORTANT: Les middlewares s'exécutent dans l'ordre INVERSE de leur ajout
# Ordre d'ajout : CORS → Auth → SetupRedirect
# Ordre d'exécution : SetupRedirect → Auth → CORS
#
# SetupRedirect s'exécute en premier : redirige vers /setup si premier lancement
# Auth s'exécute ensuite : vérifie l'authentification
# CORS s'exécute en dernier : ajoute les headers CORS

# Ajouter CORS en premier (s'exécutera en dernier)
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ALLOW_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Ajouter Auth en deuxième (s'exécutera en deuxième)
app.add_middleware(AuthMiddleware)

# SetupRedirect désactivé - le frontend gère le setup via /api/setup/status
# app.add_middleware(SetupRedirectMiddleware)

# ==================== LIFECYCLE ====================

@app.on_event("startup")
async def startup():
    """Au démarrage de l'app"""
    logger.info("Version applicative: %s", APP_VERSION)
    logger.info("Initialisation de la base de données...")
    try:
        init_db()
        logger.info("Base de données initialisée")
    except Exception as e:
        logger.error("Erreur initialisation DB (version %s): %s", APP_VERSION, e)
        import traceback
        traceback.print_exc()

    logger.info("Démarrage du scheduler...")
    try:
        start_scheduler()
        logger.info("Scheduler démarré")
    except Exception as e:
        logger.warning("Erreur démarrage scheduler (version %s): %s", APP_VERSION, e)

    logger.info("Application démarrée v%s", APP_VERSION)

@app.on_event("shutdown")
async def shutdown():
    """À l'arrêt de l'app"""
    stop_scheduler()
    logger.info("Application arrêtée v%s", APP_VERSION)

# ==================== HEALTH ====================

@app.get("/health")
async def health():
    """Healthcheck simple - retourne toujours 200 si l'API répond"""
    return {
        "status": "ok",
        "timestamp": datetime.utcnow().isoformat(),
        "version": APP_VERSION
    }


@app.get("/api/info")
async def info():
    """Informations de diagnostic (version, uptime)"""
    return {
        "version": APP_VERSION,
        "uptime_seconds": int(time.time() - start_time),
        "started_at": datetime.utcfromtimestamp(start_time).isoformat() + "Z"
    }

# ==================== GRABS ====================

@app.get("/api/grabs", response_model=list[GrabOut])
async def list_grabs(limit: int = Query(50, ge=1, le=1000), tracker: str = Query("all")):
    """Liste les derniers grabs avec filtre tracker"""
    try:
        tracker_filter = None if tracker == "all" else tracker
        return get_grabs(limit, tracker_filter=tracker_filter)
    except Exception as e:
        logger.error(f"Erreur list_grabs: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/trackers")
async def list_trackers():
    """Récupère la liste des trackers disponibles"""
    try:
        trackers = get_trackers()
        return {"trackers": trackers}
    except Exception as e:
        logger.error(f"Erreur list_trackers: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/stats", response_model=GrabStats)
async def get_grabs_stats():
    """Récupère les statistiques complètes"""
    try:
        return get_stats()
    except Exception as e:
        logger.error(f"Erreur get_stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ==================== RSS ====================

def _slugify_tracker_name(name: str) -> str:
    raw = str(name or "").strip().lower()
    raw = re.sub(r"[^a-z0-9]+", "-", raw)
    raw = re.sub(r"-{2,}", "-", raw).strip("-")
    return raw or "tracker"


def _resolve_tracker_name(tracker_input: str) -> str:
    from db import get_trackers

    trackers = get_trackers()
    if not trackers:
        raise HTTPException(status_code=404, detail="Aucun tracker disponible")

    # 1) Compatibilité: nom exact
    for tracker in trackers:
        if tracker == tracker_input:
            return tracker

    # 2) Nom slugifié (plus stable pour trackers personnalisés)
    slug_map = {}
    for tracker in trackers:
        slug = _slugify_tracker_name(tracker)
        if slug not in slug_map:
            slug_map[slug] = tracker

    resolved = slug_map.get(_slugify_tracker_name(tracker_input))
    if resolved:
        return resolved

    raise HTTPException(status_code=404, detail="Tracker introuvable")

@app.get("/rss")
async def rss_feed(request: Request, tracker: str = Query("all")):
    """Flux RSS standard avec filtres optionnels"""
    try:
        request_host = request.headers.get("host")
        tracker_filter = None if tracker == "all" else tracker
        rss_xml = generate_rss(request_host=request_host, tracker_filter=tracker_filter, limit=100)
        return Response(
            content=rss_xml,
            media_type="application/rss+xml; charset=utf-8"
        )
    except Exception as e:
        logger.error(f"Erreur rss_feed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/rss/torrent.json")
async def rss_torrent_json(request: Request, tracker: str = Query("all")):
    """Flux au format JSON avec filtres optionnels"""
    try:
        request_host = request.headers.get("host")
        tracker_filter = None if tracker == "all" else tracker
        json_data = generate_torrent_json(request_host=request_host, tracker_filter=tracker_filter, limit=100)
        return JSONResponse(json_data)
    except Exception as e:
        logger.error(f"Erreur rss_torrent_json: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/rss/tracker/{tracker_name}")
async def rss_tracker(request: Request, tracker_name: str):
    """Flux RSS pour un tracker spécifique"""
    try:
        request_host = request.headers.get("host")
        tracker_filter = _resolve_tracker_name(tracker_name)
        rss_xml = generate_rss(request_host=request_host, tracker_filter=tracker_filter, limit=100)
        return Response(
            content=rss_xml,
            media_type="application/rss+xml; charset=utf-8"
        )
    except Exception as e:
        logger.error(f"Erreur rss_tracker: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/rss/tracker/{tracker_name}/json")
async def rss_tracker_json(request: Request, tracker_name: str):
    """Flux JSON pour un tracker spécifique"""
    try:
        request_host = request.headers.get("host")
        tracker_filter = _resolve_tracker_name(tracker_name)
        json_data = generate_torrent_json(request_host=request_host, tracker_filter=tracker_filter, limit=100)
        return JSONResponse(json_data)
    except Exception as e:
        logger.error(f"Erreur rss_tracker_json: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Alias
@app.get("/rss.xml")
async def rss_xml_alias(request: Request, tracker: str = Query("all")):
    return await rss_feed(request, tracker)

@app.get("/feed")
async def feed_alias(request: Request, tracker: str = Query("all")):
    return await rss_feed(request, tracker)

# ==================== MAINTENANCE ====================

@app.post("/api/purge/all")
async def purge_all_grabs():
    """Supprime TOUS les grabs"""
    try:
        count = purge_all()
        return {
            "status": "cleared",
            "message": f"{count} grabs supprimés",
            "count": count
        }
    except Exception as e:
        logger.error(f"Erreur purge_all: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/purge/retention")
async def purge_retention(hours: int = Query(..., ge=1)):
    """Supprime les grabs plus anciens que X heures"""
    try:
        count = purge_by_retention(hours)
        return {
            "status": "purged",
            "message": f"Grabs > {hours}h supprimés",
            "count": count
        }
    except Exception as e:
        logger.error(f"Erreur purge_retention: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ==================== SYNC ====================

@app.get("/api/sync/status", response_model=SyncStatus)
async def sync_status():
    """Statut de la réconciliation history."""
    try:
        return get_sync_status()
    except Exception as e:
        logger.error(f"Erreur sync_status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/sync/trigger")
async def sync_trigger_now():
    """Lance une réconciliation history immédiate."""
    try:
        success = trigger_sync()
        if success:
            return {
                "status": "triggered",
                "message": "Réconciliation history lancée"
            }
        else:
            return {
                "status": "already_running",
                "message": "Une synchronisation est déjà en cours"
            }
    except Exception as e:
        logger.error(f"Erreur sync_trigger: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/sync/logs")
async def sync_logs(limit: int = Query(20, ge=1, le=100)):
    """Récupère l'historique des syncs"""
    try:
        return get_sync_logs(limit)
    except Exception as e:
        logger.error(f"Erreur sync_logs: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ==================== CONFIGURATION ====================

@app.get("/api/config")
async def get_configuration():
    """Récupère toute la configuration depuis settings.yml"""
    try:
        from setup import get_config_for_ui
        config = get_config_for_ui()
        return config
    except Exception as e:
        logger.error(f"Erreur get_config: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/config")
async def update_configuration(config_data: dict):
    """Met à jour la configuration dans settings.yml"""
    try:
        from setup import save_config_from_ui
        from setup import get_config_for_ui

        # Supporter les updates partielles (ex: bascule auth inline)
        # en fusionnant avec la config UI complète courante.
        merged_config = get_config_for_ui()
        for key, value in (config_data or {}).items():
            merged_config[key] = value

        success = save_config_from_ui(merged_config)

        if success:
            try:
                from config import reload_config
                reload_config()
                from scheduler import restart_scheduler_after_setup
                restart_scheduler_after_setup()
            except Exception as e:
                logger.warning("Erreur rechargement config/scheduler: %s", e)
            return {
                "status": "updated",
                "message": f"Configuration sauvegardée dans {SETTINGS_FILE}. Redémarrez l'application pour appliquer certains paramètres."
            }
        else:
            raise HTTPException(status_code=500, detail="Erreur lors de la sauvegarde")
    except Exception as e:
        logger.error(f"Erreur update_config: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ==================== WEBHOOK GRAB ====================

@app.post("/api/webhook/grab")
async def webhook_grab(request: Request):
    """Webhook Grab Radarr/Sonarr"""
    if not WEBHOOK_ENABLED:
        raise HTTPException(status_code=403, detail="Webhook désactivé")
    if HISTORY_INGESTION_MODE == "history_only":
        return {"status": "ignored", "reason": "ingestion_mode=history_only"}

    token = request.headers.get("X-Webhook-Token") or request.query_params.get("token")
    if not WEBHOOK_TOKEN or token != WEBHOOK_TOKEN:
        raise HTTPException(status_code=401, detail="Token webhook invalide")

    payload = await request.json()
    result = handle_webhook_grab(
        payload=payload,
        prowlarr_url=PROWLARR_URL,
        prowlarr_api_key=PROWLARR_API_KEY,
        min_score=WEBHOOK_MIN_SCORE,
        strict=WEBHOOK_STRICT,
        download=WEBHOOK_DOWNLOAD
    )
    return result


@app.post("/api/webhook/token/generate")
async def generate_webhook_token_endpoint(enable: bool = Query(False)):
    """Génère et sauvegarde un token webhook"""
    token = generate_webhook_token()
    try:
        import setup
        webhook_update = {"token": token}
        if enable:
            webhook_update["enabled"] = True
        setup.update_config({"webhook": webhook_update})
        from config import reload_config
        reload_config()
    except Exception as e:
        logger.warning("Erreur sauvegarde token webhook: %s", e)
    return {"success": True, "token": token, "enabled": enable}

# ==================== API KEYS & RSS ====================

@app.get("/api/auth/keys")
async def get_api_keys():
    """Récupère les API keys actuelles"""
    try:
        from auth import get_api_keys
        keys = get_api_keys()
        return {
            "keys": keys,
            "count": len(keys)
        }
    except Exception as e:
        logger.error(f"Erreur get_api_keys: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/auth/security-status")
async def get_auth_security_status(request: Request):
    """Retourne l'état sécurité/auth pour l'UI config."""
    try:
        auth_enabled = is_auth_enabled()
        session_token = request.cookies.get("session_token")
        client_host = request.client.host if request.client else None
        if auth_enabled and not verify_session(session_token):
            raise HTTPException(status_code=401, detail="Non authentifié")
        if not auth_enabled and not is_local_request(client_host):
            raise HTTPException(status_code=403, detail="Accès local requis")

        auth_cfg = get_auth_config() or {}
        return {
            "auth_enabled": bool(auth_cfg.get("enabled", False)),
            "username": (auth_cfg.get("username") or "").strip(),
            "password_configured": bool(auth_cfg.get("password_hash")),
            "cookie_secure": bool(auth_cfg.get("cookie_secure", False)),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Erreur auth security-status: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/auth/configure")
async def configure_auth_settings(payload: dict, request: Request, response: Response):
    """
    Configure les credentials et/ou active/désactive l'auth.
    Utilisable en mode local quand auth désactivée, sinon session requise.
    """
    try:
        auth_was_enabled = is_auth_enabled()
        session_token = request.cookies.get("session_token")
        client_host = request.client.host if request.client else None

        if auth_was_enabled and not verify_session(session_token):
            raise HTTPException(status_code=401, detail="Non authentifié")
        if not auth_was_enabled and not is_local_request(client_host):
            raise HTTPException(status_code=403, detail="Accès local requis")

        auth_cfg = get_auth_config() or {}

        username_in = str((payload or {}).get("username", "")).strip()
        password_in = str((payload or {}).get("password", "")).strip()
        enabled_in = (payload or {}).get("enabled", None)

        if username_in:
            if len(username_in) < 3:
                raise HTTPException(status_code=400, detail="Nom d'utilisateur trop court")
            auth_cfg["username"] = username_in

        if password_in:
            if len(password_in) < 8:
                raise HTTPException(status_code=400, detail="Mot de passe trop court (min 8)")
            auth_cfg["password_hash"] = hash_password(password_in)

        if enabled_in is not None:
            enable_target = bool(enabled_in)
            if enable_target and (not auth_cfg.get("username") or not auth_cfg.get("password_hash")):
                raise HTTPException(
                    status_code=400,
                    detail="Configurer utilisateur + mot de passe avant activation"
                )
            auth_cfg["enabled"] = enable_target

        if "cookie_secure" in (payload or {}):
            auth_cfg["cookie_secure"] = bool((payload or {}).get("cookie_secure"))

        if not save_auth_config(auth_cfg):
            raise HTTPException(status_code=500, detail="Erreur sauvegarde configuration auth")

        try:
            from config import reload_config
            reload_config()
        except Exception as e:
            logger.warning("Erreur reload_config après auth configure: %s", e)

        enabled_now = bool(auth_cfg.get("enabled", False))
        if (not auth_was_enabled) and enabled_now and not verify_session(session_token):
            # Evite de verrouiller l'interface juste après activation.
            new_session = create_session()
            response.set_cookie(
                key="session_token",
                value=new_session,
                httponly=True,
                secure=get_auth_cookie_secure(),
                samesite="lax",
                max_age=7 * 24 * 3600
            )

        return {
            "success": True,
            "auth_enabled": enabled_now,
            "username": (auth_cfg.get("username") or "").strip(),
            "password_configured": bool(auth_cfg.get("password_hash")),
            "cookie_secure": bool(auth_cfg.get("cookie_secure", False)),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Erreur configure auth: %s", e)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/auth/keys/generate")
async def generate_api_key_endpoint(request: Request):
    """Génère une nouvelle API key"""
    try:
        from auth import create_api_key
        from datetime import datetime

        payload = {}
        try:
            payload = await request.json()
        except Exception:
            payload = {}

        requested_name = str(payload.get("name") or "").strip()
        # Créer une nouvelle clé avec un nom automatique si non fourni
        name = requested_name or f"API Key {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        key_data = create_api_key(name, enabled=True)

        if key_data:
            return {
                "success": True,
                "api_key": key_data["key"],
                "name": key_data["name"],
                "created_at": key_data["created_at"],
                "message": "API key générée avec succès"
            }
        else:
            raise HTTPException(status_code=500, detail="Erreur sauvegarde API key")
    except Exception as e:
        logger.error(f"Erreur generate_api_key: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/auth/keys/{key}")
async def delete_api_key(key: str):
    """Supprime une API key"""
    try:
        from auth import delete_api_key as del_key
        success = del_key(key)

        if success:
            return {
                "success": True,
                "message": "API key supprimée"
            }
        else:
            raise HTTPException(status_code=404, detail="API key non trouvée")
    except Exception as e:
        logger.error(f"Erreur delete_api_key: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/rss/urls")
async def get_rss_urls(request: Request, token: Optional[str] = Query(None)):
    """Génère les URLs RSS avec token sélectionnable et trackers normalisés."""
    try:
        from auth import get_api_keys
        from config import RSS_DOMAIN, RSS_SCHEME

        # Récupérer les API keys disponibles
        keys = get_api_keys()
        if not keys:
            return {
                "error": "Aucune API key disponible",
                "message": "Générez une API key d'abord depuis le dashboard",
                "urls": []
            }

        enabled_keys = [k for k in keys if k.get("enabled", True)]
        if not enabled_keys:
            return {
                "error": "Aucune API key active",
                "message": "Activez une API key depuis le dashboard",
                "urls": [],
                "api_keys": []
            }

        # Token choisi par l'utilisateur (si fourni) sinon première active
        api_key_data = None
        if token:
            api_key_data = next((k for k in enabled_keys if k.get("key") == token), None)
        if api_key_data is None:
            api_key_data = enabled_keys[0]

        # Liste des tokens nommés (actifs) exposés à l'UI
        api_keys_public = [
            {"name": k.get("name") or "API Key", "key": k.get("key")}
            for k in enabled_keys
        ]

        if not api_key_data:
            return {
                "error": "Aucune API key active",
                "message": "Activez une API key depuis le dashboard",
                "urls": [],
                "api_keys": []
            }

        api_key = api_key_data["key"]
        api_key_encoded = quote(api_key, safe="")

        # Construire l'URL de base
        base_url = f"{RSS_SCHEME}://{RSS_DOMAIN}"

        # Générer les URLs avec token dans query string
        urls = [
            {
                "name": "Flux RSS complet",
                "url": f"{base_url}/rss?apikey={api_key_encoded}",
                "description": "Tous les torrents récents",
                "category": "principal"
            },
            {
                "name": "Flux RSS (format JSON)",
                "url": f"{base_url}/rss/torrent.json?apikey={api_key_encoded}",
                "description": "Format JSON pour intégrations",
                "category": "principal"
            }
        ]

        # Ajouter les URLs par tracker avec slug normalisé
        from db import get_trackers
        trackers = get_trackers()
        for tracker in trackers[:10]:  # Limiter à 10 trackers
            tracker_slug = _slugify_tracker_name(tracker)
            urls.append({
                "name": f"Flux {tracker}",
                "url": f"{base_url}/rss/tracker/{tracker_slug}?apikey={api_key_encoded}",
                "description": f"Torrents de {tracker} uniquement",
                "category": "tracker",
                "tracker": tracker,
                "tracker_slug": tracker_slug
            })

        return {
            "api_key": api_key,
            "api_key_name": api_key_data.get("name", "Sans nom"),
            "api_keys": api_keys_public,
            "selected_api_key": {
                "name": api_key_data.get("name", "Sans nom"),
                "key": api_key
            },
            "base_url": base_url,
            "auth": {
                "x_api_key": api_key,
                "authorization": f"Bearer {api_key}"
            },
            "urls": urls,
            "total_urls": len(urls)
        }
    except Exception as e:
        logger.error(f"Erreur get_rss_urls: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ==================== ADMIN / MAINTENANCE ====================

@app.post("/api/cache/clear")
async def clear_cache():
    """Vide le cache trackers."""
    try:
        # Cache trackers
        from prowlarr import clear_tracker_cache, get_tracker_cache_info
        tracker_count = clear_tracker_cache()

        return {
            "status": "cleared",
            "message": f"Cache vidé ({tracker_count} trackers)",
            "tracker_cache_cleared": tracker_count
        }
    except Exception as e:
        logger.error(f"Erreur clear_cache: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/db/vacuum")
async def vacuum_db():
    """Optimise la base de données SQLite (VACUUM)"""
    try:
        size_before, size_after = vacuum_database()
        saved = size_before - size_after
        
        return {
            "status": "optimized",
            "message": "Base de données optimisée",
            "size_before_mb": round(size_before, 2),
            "size_after_mb": round(size_after, 2),
            "saved_mb": round(saved, 2)
        }
    except Exception as e:
        logger.error(f"Erreur vacuum_db: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/logs/system")
async def get_system_logs(
    limit: int = Query(100, ge=1, le=500),
    level: str = Query("all")
):
    """
    Récupère les logs système avec filtrage
    level: all, success, error, warning, info
    """
    try:
        # Récupérer les logs de sync
        sync_logs = get_sync_logs(limit)
        
        # Formater les logs
        logs = []
        for log in sync_logs:
            log_level = "success" if log["status"] == "success" else "error"
            log_type = "sync"
            message = f"Sync: {log['grabs_count']} grabs, {log.get('deduplicated_count', 0)} doublons"
            details = log.get("error", None)
            
            logs.append({
                "timestamp": log["sync_at"],
                "level": log_level,
                "type": log_type,
                "message": message,
                "details": details
            })
        
        # Filtrer par niveau
        if level != "all":
            logs = [l for l in logs if l["level"] == level]
        
        return {
            "logs": logs[:limit],
            "total": len(logs),
            "level": level
        }
    except Exception as e:
        logger.error(f"Erreur get_system_logs: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/stats/detailed")
async def get_detailed_stats():
    """Statistiques système détaillées"""
    try:
        # Stats DB
        db_stats = get_db_stats()
        
        # Stats torrents
        torrent_count = len(list(TORRENT_DIR.glob("*.torrent"))) if TORRENT_DIR.exists() else 0
        torrent_size = sum(f.stat().st_size for f in TORRENT_DIR.glob("*.torrent")) / (1024 * 1024) if TORRENT_DIR.exists() else 0
        
        # Stats système
        process = psutil.Process()
        memory_mb = process.memory_info().rss / (1024 * 1024)
        cpu_percent = process.cpu_percent(interval=0.1)
        uptime_seconds = int(time.time() - start_time)
        
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "database": db_stats,
            "torrents": {
                "count": torrent_count,
                "total_size_mb": round(torrent_size, 2),
                "directory": str(TORRENT_DIR)
            },
            "system": {
                "memory_mb": round(memory_mb, 2),
                "cpu_percent": round(cpu_percent, 2),
                "threads": process.num_threads(),
                "uptime_seconds": uptime_seconds
            }
        }
    except Exception as e:
        logger.error(f"Erreur get_detailed_stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ==================== TORRENTS MANAGEMENT ====================

@app.get("/api/torrents")
async def list_torrents():
    """Liste tous les fichiers torrents avec leurs informations détaillées"""
    try:
        torrents = get_torrent_files_with_info()
        total_size_mb = round(sum(float(t.get("size_mb", 0) or 0) for t in torrents), 2)
        with_grab_count = sum(1 for t in torrents if t.get("has_grab"))
        orphan_count = len(torrents) - with_grab_count
        return {
            "torrents": torrents,
            "total": len(torrents),
            "summary": {
                "total_size_mb": total_size_mb,
                "with_grab_count": with_grab_count,
                "orphan_count": orphan_count,
            },
        }
    except Exception as e:
        logger.error(f"Erreur list_torrents: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/torrents/cleanup-orphans")
async def cleanup_torrents():
    """Supprime les fichiers torrents orphelins (sans grab associé)"""
    try:
        deleted_count, deleted_files = cleanup_orphan_torrents()
        return {
            "status": "cleaned",
            "message": f"{deleted_count} torrents orphelins supprimés",
            "deleted_count": deleted_count,
            "deleted_files": deleted_files
        }
    except Exception as e:
        logger.error(f"Erreur cleanup_torrents: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/torrents/{filename}")
async def delete_torrent(filename: str):
    """Supprime un fichier torrent spécifique"""
    try:
        if resolve_torrent_path(filename) is None:
            raise HTTPException(status_code=400, detail="Nom de fichier torrent invalide")
        success = delete_torrent_file(filename)
        if success:
            return {
                "status": "deleted",
                "message": f"Torrent {filename} supprimé",
                "filename": filename
            }
        else:
            raise HTTPException(status_code=404, detail=f"Torrent {filename} non trouvé")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur delete_torrent: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/torrents/download/{filename}")
async def download_torrent_file(filename: str):
    """Télécharge un fichier torrent même si /torrents statique est désactivé."""
    try:
        path = resolve_torrent_path(filename)
        if path is None or not path.exists():
            raise HTTPException(status_code=404, detail="Torrent non trouvé")
        return FileResponse(
            path=str(path),
            media_type="application/x-bittorrent",
            filename=path.name
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Erreur download_torrent_file %s: %s", filename, e)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/torrents/purge-all")
async def purge_torrents():
    """Supprime TOUS les fichiers torrents"""
    try:
        deleted_count, size_freed = purge_all_torrents()
        return {
            "status": "purged",
            "message": f"{deleted_count} torrents supprimés ({size_freed} MB libérés)",
            "deleted_count": deleted_count,
            "size_freed_mb": size_freed
        }
    except Exception as e:
        logger.error(f"Erreur purge_torrents: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/logs/{log_id}")
async def delete_sync_log(log_id: int):
    """Supprime un log de synchronisation spécifique"""
    try:
        success = delete_log(log_id)
        if success:
            return {
                "status": "deleted",
                "message": f"Log {log_id} supprimé",
                "log_id": log_id
            }
        else:
            raise HTTPException(status_code=404, detail=f"Log {log_id} non trouvé")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur delete_sync_log: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/logs/purge-all")
async def purge_logs():
    """Supprime tous les logs de synchronisation"""
    try:
        deleted_count = purge_all_logs()
        return {
            "status": "purged",
            "message": f"{deleted_count} logs supprimés",
            "deleted_count": deleted_count
        }
    except Exception as e:
        logger.error(f"Erreur purge_logs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/db/purge-all")
async def purge_database():
    """Nettoie la base (grabs, logs, sessions) sans toucher la config."""
    try:
        counts = purge_all_db()
        return {
            "status": "purged",
            "message": (
                f"DB nettoyée: {counts['grabs']} grabs, "
                f"{counts['logs']} logs, {counts['sessions']} sessions"
            ),
            "counts": counts
        }
    except Exception as e:
        logger.error(f"Erreur purge_db: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/history/reconcile/sync")
async def sync_history_reconcile_endpoint(
    event_type: Optional[str] = Query("grabbed"),
    page_size: int = Query(200, ge=50, le=500),
    max_pages: int = Query(10, ge=1, le=50),
    lookback_days: Optional[int] = Query(None, ge=1, le=365),
    full_scan: bool = Query(False),
    download_from_history: Optional[bool] = Query(None),
    min_score: Optional[int] = Query(None, ge=0, le=10),
    strict_hash: Optional[bool] = Query(None),
):
    """Rafraichit l'historique consolide Radarr/Sonarr."""
    try:
        apps = setup.get_history_apps()
        result = sync_grab_history(
            history_apps=apps,
            event_type=event_type or "",
            page_size=page_size,
            max_pages=max_pages,
            lookback_days=lookback_days or HISTORY_LOOKBACK_DAYS,
            full_scan=full_scan,
            download_from_history=HISTORY_DOWNLOAD_FROM_HISTORY if download_from_history is None else download_from_history,
            min_score=HISTORY_MIN_SCORE if min_score is None else min_score,
            strict_hash=HISTORY_STRICT_HASH if strict_hash is None else strict_hash,
            ingestion_mode=HISTORY_INGESTION_MODE,
        )
        return {"status": "ok", "result": result}
    except Exception as e:
        logger.error("Erreur sync historique consolide: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/history/reconcile")
async def list_history_reconcile(
    limit: int = Query(200, ge=1, le=1000),
    instance: Optional[str] = Query(None),
    tracker: Optional[str] = Query(None),
    download_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    source: Optional[str] = Query(None),
    dedup: bool = Query(True)
):
    """Liste l'historique consolide avec indicateur webhook."""
    try:
        rows = get_grab_history_list(
            limit=limit,
            instance=instance,
            tracker=tracker,
            download_id=download_id,
            status=status,
            source=source,
            dedup=dedup
        )
        if rows:
            return rows

        # Compat legacy: si store historique vide, fallback sur grabs canoniques.
        fallback_rows = []
        grabs_rows = get_grabs(limit=1000, tracker_filter=None)
        for row in grabs_rows:
            row_instance = row.get("instance")
            row_tracker = row.get("tracker")
            row_download_id = row.get("download_id")
            row_status = row.get("status")
            row_source = row.get("source_first_seen") or row.get("source_last_seen")

            if instance and row_instance != instance:
                continue
            if tracker and row_tracker != tracker:
                continue
            if download_id and row_download_id != download_id:
                continue
            if status and row_status != status:
                continue
            if source and row_source != source:
                continue

            fallback_rows.append({
                "id": row.get("id"),
                "instance": row_instance,
                "download_id": row_download_id,
                "source_title": row.get("title"),
                "indexer": row_tracker,
                "size": None,
                "grabbed_at": row.get("grabbed_at"),
                "torrent_file": row.get("torrent_file"),
                "status": row_status or "missing",
                "source": row_source or "legacy",
                "source_last_seen": row.get("source_last_seen"),
                "in_webhook": 1 if (row_source or "").lower() == "webhook" else 0
            })

        fallback_rows.sort(
            key=lambda item: item.get("grabbed_at") or "",
            reverse=True
        )
        logger.warning(
            "historique consolide vide: fallback sur grabs (%s lignes retournees)",
            len(fallback_rows[:limit])
        )
        return fallback_rows[:limit]
    except Exception as e:
        logger.error("Erreur historique consolide list: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/history/reconcile/recover")
async def recover_history_reconcile(payload: dict):
    """Recupere un torrent manquant a partir de l'historique consolide."""
    download_id = (payload.get("download_id") or "").strip()
    instance = (payload.get("instance") or "").strip() or None
    if not download_id:
        raise HTTPException(status_code=400, detail="download_id manquant")

    record = get_grab_history_record(download_id=download_id, instance=instance)
    if not record:
        raise HTTPException(status_code=404, detail="Entrée historique introuvable")

    record_instance = (record.get("instance") or instance or "").strip().lower()

    with get_db() as conn:
        existing = conn.execute(
            """
            SELECT 1
            FROM grabs
            WHERE instance = ? AND download_id = ?
            LIMIT 1
            """,
            (record_instance, download_id)
        ).fetchone()
    if existing:
        return {"status": "exists", "message": "Déjà présent dans les grabs"}

    if not PROWLARR_URL or not PROWLARR_API_KEY:
        raise HTTPException(status_code=400, detail="Prowlarr non configuré")

    release_title = record.get("source_title") or download_id
    record_payload = {
        "instance": record_instance,
        "download_id": download_id,
        "source_title": release_title,
        "indexer": record.get("indexer"),
        "size": record.get("size"),
        "info_url": record.get("info_url")
    }
    result = recover_from_history(
        record=record_payload,
        prowlarr_url=PROWLARR_URL,
        prowlarr_api_key=PROWLARR_API_KEY,
        min_score=HISTORY_MIN_SCORE,
        strict=HISTORY_STRICT_HASH,
        download=True
    )
    return result

# ==================== WEB UI ====================

# ==================== HTML PAGES ====================

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Page de connexion moderne et responsive"""
    return templates.TemplateResponse("pages/login.html", {"request": request, "version": APP_VERSION})


def _ui_context_or_redirect(request: Request):
    # Premier lancement ? Rediriger vers setup
    first_run = setup.is_first_run()
    if first_run:
        return RedirectResponse(url='/setup', status_code=302)

    # Auth activée ?
    auth_enabled = is_auth_enabled()
    if auth_enabled:
        session_token = request.cookies.get('session_token')
        authenticated = verify_session(session_token)

        # Non authentifié ? Rediriger AVANT le rendu
        if not authenticated:
            return RedirectResponse(url='/login', status_code=302)

        username = get_username_from_session(session_token) or ""
    else:
        authenticated = False
        username = ""

    return {
        "request": request,
        "first_run": first_run,
        "auth_enabled": auth_enabled,
        "authenticated": authenticated,
        "username": username,
        "version": APP_VERSION
    }


@app.get("/", response_class=HTMLResponse)
async def web_ui(request: Request):
    """Interface web principale - Redirection serveur si non authentifié"""
    ctx = _ui_context_or_redirect(request)
    if isinstance(ctx, RedirectResponse):
        return ctx

    # Authentifié ou auth désactivée : retourner le HTML
    return templates.TemplateResponse("pages/overview.html", ctx)


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(request: Request):
    """Page dashboard (alias de /)"""
    return RedirectResponse(url='/overview', status_code=302)


@app.get("/overview", response_class=HTMLResponse)
async def overview_page(request: Request):
    ctx = _ui_context_or_redirect(request)
    if isinstance(ctx, RedirectResponse):
        return ctx
    return templates.TemplateResponse("pages/overview.html", ctx)


@app.get("/grabs", response_class=HTMLResponse)
async def grabs_page(request: Request):
    ctx = _ui_context_or_redirect(request)
    if isinstance(ctx, RedirectResponse):
        return ctx
    return templates.TemplateResponse("pages/grabs.html", ctx)


@app.get("/torrents", response_class=HTMLResponse)
async def torrents_page(request: Request):
    ctx = _ui_context_or_redirect(request)
    if isinstance(ctx, RedirectResponse):
        return ctx
    return templates.TemplateResponse("pages/torrents.html", ctx)


@app.get("/rss-ui", response_class=HTMLResponse)
async def rss_ui_page(request: Request):
    ctx = _ui_context_or_redirect(request)
    if isinstance(ctx, RedirectResponse):
        return ctx
    return templates.TemplateResponse("pages/rss.html", ctx)


@app.get("/config", response_class=HTMLResponse)
async def configuration_page(request: Request):
    ctx = _ui_context_or_redirect(request)
    if isinstance(ctx, RedirectResponse):
        return ctx
    return templates.TemplateResponse("pages/configuration.html", ctx)


@app.get("/security", response_class=HTMLResponse)
async def security_page(request: Request):
    return RedirectResponse(url='/config?tab=security', status_code=302)


@app.get("/logs", response_class=HTMLResponse)
async def logs_page(request: Request):
    return RedirectResponse(url='/config?tab=maintenance', status_code=302)


@app.get("/history-grabb", response_class=HTMLResponse)
async def history_grabb_page(request: Request):
    return RedirectResponse(url='/grabs', status_code=302)
