# api.py
from fastapi import FastAPI, HTTPException, Query, Request, Cookie
from fastapi.responses import Response, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from pathlib import Path
import logging
import psutil
import time
from datetime import datetime
from typing import Optional

from config import TORRENT_DIR, DB_PATH, DEDUP_HOURS, DESCRIPTIONS, PROWLARR_URL, PROWLARR_API_KEY
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

logger = logging.getLogger(__name__)

# Variable pour tracker le temps de démarrage
start_time = time.time()

app = FastAPI(
    title="Grab2RSS API",
    description="API pour Grab2RSS - Convert Prowlarr grabs en RSS",
    version="2.6.1"
)

# Configuration des templates et fichiers statiques
# Utiliser un chemin absolu pour éviter les problèmes de résolution de chemin
TEMPLATE_DIR = Path(__file__).parent.absolute() / "templates"
STATIC_DIR = Path(__file__).parent.absolute() / "static"

templates = Jinja2Templates(directory=str(TEMPLATE_DIR))

# Middleware d'authentification simplifié
class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Si auth désactivée, tout est public
        if not is_auth_enabled():
            return await call_next(request)

        # Routes toujours publiques même si auth activée
        public_routes = [
            '/health',
            '/debug',
            '/login',
            '/setup',
            '/api/auth/login',
            '/api/auth/status',
            '/api/setup',
            '/static',
            '/torrents'
        ]

        # Vérifier si route publique
        for route in public_routes:
            if request.url.path.startswith(route):
                return await call_next(request)

        # Routes RSS : accès local ou API key
        if request.url.path.startswith('/rss') or request.url.path.startswith('/feed'):
            client_host = request.client.host if request.client else None
            if is_local_request(client_host):
                return await call_next(request)

            api_key = request.query_params.get('api_key')
            if api_key and verify_api_key(api_key):
                return await call_next(request)

            raise HTTPException(status_code=401, detail="Non autorisé")

        # Autres routes : vérifier session
        session_token = request.cookies.get('session_token')
        if not verify_session(session_token):
            # Pages HTML : retourner la page (le frontend gérera)
            # API : retourner 401
            if request.url.path.startswith('/api'):
                raise HTTPException(status_code=401, detail="Non authentifié")

        return await call_next(request)


# SetupRedirectMiddleware SUPPRIMÉ
# La logique de redirection vers /setup est maintenant gérée côté frontend via window.INITIAL_STATE
# pour être compatible avec oauth2-proxy (pas de redirections serveur HTTP 302)

# Inclure les routes AVANT les middlewares pour qu'ils soient bien pris en compte
app.include_router(setup_router)
app.include_router(auth_router)

# Monter les fichiers statiques
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
if TORRENT_DIR.exists():
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
    allow_origins=["*"],
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
    print("🔧 Initialisation de la base de données...")
    try:
        init_db()
        print("✅ Base de données initialisée")
    except Exception as e:
        print(f"❌ Erreur initialisation DB: {e}")
        import traceback
        traceback.print_exc()

    print("🔧 Démarrage du scheduler...")
    try:
        start_scheduler()
        print("✅ Scheduler démarré")
    except Exception as e:
        print(f"⚠️  Erreur démarrage scheduler: {e}")

    print("✅ Application démarrée v2.9.0")

@app.on_event("shutdown")
async def shutdown():
    """À l'arrêt de l'app"""
    stop_scheduler()
    print("✅ Application arrêtée")

# ==================== HEALTH ====================

@app.get("/health")
async def health():
    """Healthcheck simple - retourne toujours 200 si l'API répond"""
    return {
        "status": "ok",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "2.9.0"
    }

@app.get("/debug")
async def debug_info():
    """Informations de debug"""
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
                "message": "Configuration sauvegardée dans /config/settings.yml. Redémarrez l'application pour appliquer certains paramètres (SYNC_INTERVAL, etc.)"
            }
        else:
            raise HTTPException(status_code=500, detail="Erreur lors de la sauvegarde")
    except Exception as e:
        logger.error(f"Erreur update_config: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ==================== ADMIN / MAINTENANCE v2.6.8 ====================

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
            "output_file": results.get("output_file", "/config/history_limits_test.json")
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
async def test_ui():
    """Interface de test simple"""
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
async def minimal_ui():
    """Interface ultra-minimaliste"""
    return """<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <title>Grab2RSS - Test Minimal</title>
</head>
<body style="font-family: Arial; max-width: 800px; margin: 50px auto; padding: 20px; background: #0f0f0f; color: #fff;">
    <h1 style="color: #1e90ff;">🧪 Grab2RSS v2.6.8 - Test Minimal</h1>
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
    return templates.TemplateResponse("pages/login.html", {"request": request})


@app.get("/", response_class=HTMLResponse)
async def web_ui(request: Request):
    """Interface web principale - Toujours retourne HTTP 200"""
    # État d'authentification
    auth_enabled = is_auth_enabled()
    authenticated = False
    username = ""

    if auth_enabled:
        session_token = request.cookies.get('session_token')
        authenticated = verify_session(session_token)
        if authenticated:
            username = get_username_from_session(session_token) or ""

    # Premier lancement ?
    first_run = setup.is_first_run()

    # Retourner le HTML - le frontend gère la navigation
    return templates.TemplateResponse("pages/dashboard.html", {
        "request": request,
        "first_run": first_run,
        "auth_enabled": auth_enabled,
        "authenticated": authenticated,
        "username": username
    })


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(request: Request):
    """Page dashboard (alias de /)"""
    # Utiliser la même logique que la route /
    return await web_ui(request)
