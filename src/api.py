# api.py
from fastapi import FastAPI, HTTPException, Query, Request, Cookie
from fastapi.responses import Response, HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
import logging
import psutil
import time
from datetime import datetime
from typing import Optional

from logging_config import setup_logging
from version import APP_VERSION
from config import TORRENT_DIR, DB_PATH, DEDUP_HOURS, DESCRIPTIONS, PROWLARR_URL, PROWLARR_API_KEY, CORS_ALLOW_ORIGINS, TORRENTS_EXPOSE_STATIC
from db import (
    init_db, get_grabs, get_stats, purge_all, purge_by_retention,
    get_config, set_config, get_all_config, get_sync_logs, get_trackers, get_db,
    vacuum_database, get_db_stats, get_torrent_files_with_info, cleanup_orphan_torrents,
    delete_torrent_file, purge_all_torrents, delete_log, purge_all_logs
)
from rss import generate_rss, generate_torrent_json
from models import GrabOut, GrabStats, SyncStatus
from scheduler import start_scheduler, stop_scheduler, get_sync_status, trigger_sync
import setup
from setup_routes import router as setup_router
from auth_routes import router as auth_router
from auth import is_auth_enabled, verify_session, verify_api_key, is_local_request, get_username_from_session

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
from paths import TEMPLATES_DIR, STATIC_DIR, SETTINGS_FILE, CONFIG_DIR

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
            return await call_next(request)

        # Routes toujours publiques même si auth activée
        public_routes = [
            '/health',              # Healthcheck pour Docker/K8s
            '/login',               # Page de login
            '/api/auth/login',      # API login
            '/api/auth/status',     # Statut auth
            '/api/info'             # Infos version/uptime
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
        if request.url.path.startswith('/rss') or request.url.path.startswith('/feed'):
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

@app.get("/debug")
async def debug_info(request: Request):
    """Informations de debug - Protégé"""
    from fastapi.responses import RedirectResponse

    # Vérifier auth si activée
    if is_auth_enabled():
        session_token = request.cookies.get('session_token')
        if not verify_session(session_token):
            raise HTTPException(status_code=401, detail="Non authentifié")

    return {
        "status": "running",
        "timestamp": datetime.utcnow().isoformat(),
        "endpoints": [
            "/",
            "/test",
            "/health",
            "/debug",
            "/api/stats",
            "/api/grabs",
            "/rss"
        ],
        "message": "Si vous voyez ceci, l'API fonctionne correctement"
    }

# ==================== GRABS ====================

@app.get("/api/grabs", response_model=list[GrabOut])
async def list_grabs(limit: int = Query(50, ge=1, le=1000), tracker: str = Query("all")):
    """Liste les derniers grabs avec filtre tracker"""
    try:
        tracker_filter = None if tracker == "all" else tracker
        return get_grabs(limit, dedup_hours=DEDUP_HOURS, tracker_filter=tracker_filter)
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
        rss_xml = generate_rss(request_host=request_host, tracker_filter=tracker_name, limit=100)
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
        json_data = generate_torrent_json(request_host=request_host, tracker_filter=tracker_name, limit=100)
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
    """Statut du sync Prowlarr"""
    try:
        return get_sync_status()
    except Exception as e:
        logger.error(f"Erreur sync_status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/sync/trigger")
async def sync_trigger_now():
    """Lance une sync immédiate"""
    try:
        success = trigger_sync()
        if success:
            return {
                "status": "triggered",
                "message": "Synchronisation lancée"
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
        success = save_config_from_ui(config_data)

        if success:
            return {
                "status": "updated",
                "message": f"Configuration sauvegardée dans {SETTINGS_FILE}. Redémarrez l'application pour appliquer certains paramètres (SYNC_INTERVAL, etc.)"
            }
        else:
            raise HTTPException(status_code=500, detail="Erreur lors de la sauvegarde")
    except Exception as e:
        logger.error(f"Erreur update_config: {e}")
        raise HTTPException(status_code=500, detail=str(e))

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

@app.post("/api/auth/keys/generate")
async def generate_api_key_endpoint():
    """Génère une nouvelle API key"""
    try:
        from auth import create_api_key
        from datetime import datetime

        # Créer une nouvelle clé avec un nom automatique
        name = f"API Key {datetime.now().strftime('%Y-%m-%d %H:%M')}"
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
async def get_rss_urls(request: Request):
    """Génère les URLs RSS (sans API key dans l'URL)"""
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

        # Prendre la première clé active
        api_key_data = next((k for k in keys if k.get("enabled", True)), None)
        if not api_key_data:
            return {
                "error": "Aucune API key active",
                "message": "Activez une API key depuis le dashboard",
                "urls": []
            }

        api_key = api_key_data["key"]

        # Construire l'URL de base
        base_url = f"{RSS_SCHEME}://{RSS_DOMAIN}"

        # Générer les URLs (sans API key dans l'URL)
        urls = [
            {
                "name": "Flux RSS complet",
                "url": f"{base_url}/rss",
                "description": "Tous les torrents récents",
                "category": "principal"
            },
            {
                "name": "Flux RSS (format JSON)",
                "url": f"{base_url}/rss/torrent.json",
                "description": "Format JSON pour intégrations",
                "category": "principal"
            }
        ]

        # Ajouter les URLs par tracker
        from db import get_trackers
        trackers = get_trackers()
        for tracker in trackers[:10]:  # Limiter à 10 trackers
            urls.append({
                "name": f"Flux {tracker}",
                "url": f"{base_url}/rss/tracker/{tracker}",
                "description": f"Torrents de {tracker} uniquement",
                "category": "tracker"
            })

        return {
            "api_key": api_key,
            "api_key_name": api_key_data.get("name", "Sans nom"),
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
    """Vide tous les caches (trackers + imports Radarr/Sonarr)"""
    try:
        # Cache trackers
        from prowlarr import clear_tracker_cache, get_tracker_cache_info
        tracker_count = clear_tracker_cache()
        
        # Cache Radarr/Sonarr
        from radarr_sonarr import clear_cache as clear_import_cache
        clear_import_cache()
        
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

@app.post("/api/test-history-limits")
async def test_history_limits():
    """Lance le test des limites d'historique Prowlarr/Radarr/Sonarr"""
    try:
        from test_history_limits import run_test_and_save

        # Lancer le test (peut prendre quelques secondes)
        results = run_test_and_save()

        return {
            "status": "success",
            "message": "Test des limites d'historique terminé",
            "results": results,
            "output_file": results.get("output_file", str(CONFIG_DIR / "history_limits_test.json"))
        }
    except Exception as e:
        logger.error(f"Erreur test_history_limits: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ==================== TORRENTS MANAGEMENT ====================

@app.get("/api/torrents")
async def list_torrents():
    """Liste tous les fichiers torrents avec leurs informations détaillées"""
    try:
        torrents = get_torrent_files_with_info()
        return {
            "torrents": torrents,
            "total": len(torrents)
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

# ==================== WEB UI ====================

@app.get("/test", response_class=HTMLResponse)
async def test_ui(request: Request):
    """Interface de test simple - Protégée"""
    from fastapi.responses import RedirectResponse

    # Vérifier auth si activée
    if is_auth_enabled():
        session_token = request.cookies.get('session_token')
        if not verify_session(session_token):
            return RedirectResponse(url='/login', status_code=302)

    return """<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>Test</title></head>
<body style="font-family: Arial; max-width: 800px; margin: 50px auto; padding: 20px; background: #0f0f0f; color: #fff;">
<h1 style="color: #1e90ff;">🧪 Grab2RSS - Test</h1>
<p>✅ L'API fonctionne !</p>
<ul>
<li><a href="/api/stats" style="color: #1e90ff;">Voir les stats (JSON)</a></li>
<li><a href="/api/grabs" style="color: #1e90ff;">Voir les grabs (JSON)</a></li>
<li><a href="/rss" style="color: #1e90ff;">Voir le flux RSS</a></li>
<li><a href="/" style="color: #1e90ff;">Interface complète</a></li>
</ul>
</body></html>"""

@app.get("/minimal", response_class=HTMLResponse)
async def minimal_ui(request: Request):
    """Interface ultra-minimaliste - Protégée"""
    from fastapi.responses import RedirectResponse

    # Vérifier auth si activée
    if is_auth_enabled():
        session_token = request.cookies.get('session_token')
        if not verify_session(session_token):
            return RedirectResponse(url='/login', status_code=302)

    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <title>Grab2RSS - Test Minimal</title>
</head>
<body style="font-family: Arial; max-width: 800px; margin: 50px auto; padding: 20px; background: #0f0f0f; color: #fff;">
    <h1 style="color: #1e90ff;">🧪 Grab2RSS v{APP_VERSION} - Test Minimal</h1>
    <p style="color: #00ff00;">✅ Si vous voyez cette page, le serveur fonctionne !</p>
    <h2>📋 Liens de Test</h2>
    <a href="/api/stats" target="_blank" style="color: #1e90ff; display: block; padding: 10px; margin: 10px 0; background: #1a1a1a; border-radius: 4px; text-decoration: none;">📊 Stats (JSON)</a>
    <a href="/api/grabs" target="_blank" style="color: #1e90ff; display: block; padding: 10px; margin: 10px 0; background: #1a1a1a; border-radius: 4px; text-decoration: none;">📋 Grabs (JSON)</a>
    <a href="/rss" target="_blank" style="color: #1e90ff; display: block; padding: 10px; margin: 10px 0; background: #1a1a1a; border-radius: 4px; text-decoration: none;">📡 Flux RSS (XML)</a>
    <a href="/health" target="_blank" style="color: #1e90ff; display: block; padding: 10px; margin: 10px 0; background: #1a1a1a; border-radius: 4px; text-decoration: none;">💚 Health Check</a>
    <a href="/" target="_blank" style="color: #1e90ff; display: block; padding: 10px; margin: 10px 0; background: #1a1a1a; border-radius: 4px; text-decoration: none;">🏠 Interface Complète</a>
</body>
</html>"""

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
    ctx = _ui_context_or_redirect(request)
    if isinstance(ctx, RedirectResponse):
        return ctx
    return templates.TemplateResponse("pages/security.html", ctx)


@app.get("/logs", response_class=HTMLResponse)
async def logs_page(request: Request):
    ctx = _ui_context_or_redirect(request)
    if isinstance(ctx, RedirectResponse):
        return ctx
    return templates.TemplateResponse("pages/logs.html", ctx)
