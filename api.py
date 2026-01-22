# api.py
from fastapi import FastAPI, HTTPException, Query, Request, Cookie
from fastapi.responses import Response, HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
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
from auth import is_auth_enabled, verify_session, verify_api_key, is_local_request

logger = logging.getLogger(__name__)

# Variable pour tracker le temps de démarrage
start_time = time.time()

app = FastAPI(
    title="Grab2RSS API",
    description="API pour Grab2RSS - Convert Prowlarr grabs en RSS",
    version="2.6.1"
)


# Middleware d'authentification
class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Routes publiques (pas d'authentification requise)
        public_routes = [
            '/health',
            '/debug',
            '/test',
            '/minimal',
            '/setup',
            '/api/setup',
            '/api/auth/login',
            '/api/auth/status',
            '/torrents'
        ]

        # Vérifier si la route est publique
        for public_route in public_routes:
            if request.url.path.startswith(public_route):
                return await call_next(request)

        # Routes RSS - traitement spécial (API key ou accès local)
        if request.url.path.startswith('/rss') or request.url.path.startswith('/feed'):
            # Si l'auth n'est pas activée, accès libre
            if not is_auth_enabled():
                return await call_next(request)

            # Vérifier si c'est une requête locale (réseau Docker/local)
            client_host = request.client.host if request.client else None
            if is_local_request(client_host):
                return await call_next(request)

            # Sinon, vérifier l'API key dans les query params
            api_key = request.query_params.get('api_key')
            if api_key and verify_api_key(api_key):
                return await call_next(request)

            # Accès refusé
            raise HTTPException(status_code=401, detail="API key requise pour accès externe aux flux RSS")

        # Pour toutes les autres routes, vérifier l'authentification
        if not is_auth_enabled():
            # Si l'auth n'est pas activée, accès libre
            return await call_next(request)

        # Vérifier la session via le cookie
        session_token = request.cookies.get('session_token')
        if not verify_session(session_token):
            # Non authentifié - rediriger vers /login pour les pages HTML
            if not request.url.path.startswith('/api'):
                return RedirectResponse(url='/login', status_code=307)
            # Pour les API, retourner 401
            raise HTTPException(status_code=401, detail="Non authentifié")

        return await call_next(request)


# Middleware pour rediriger vers /setup si premier lancement
class SetupRedirectMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Ne pas rediriger les routes API (pour éviter les erreurs JSON)
        if request.url.path.startswith('/api'):
            return await call_next(request)

        # Ne pas rediriger si déjà sur /setup
        if request.url.path.startswith('/setup'):
            return await call_next(request)

        # Ne pas rediriger si sur /login
        if request.url.path == '/login':
            return await call_next(request)

        # Ne pas rediriger les assets statiques
        if request.url.path.startswith('/torrents'):
            return await call_next(request)

        # Ne pas rediriger les routes utilitaires
        if request.url.path in ['/health', '/debug', '/test', '/minimal']:
            return await call_next(request)

        # Ne pas rediriger les flux RSS
        if request.url.path.startswith('/rss') or request.url.path.startswith('/feed'):
            return await call_next(request)

        # Vérifier si c'est le premier lancement
        if setup.is_first_run():
            return RedirectResponse(url='/setup', status_code=307)

        return await call_next(request)

# Ajouter les middlewares (ordre important: AuthMiddleware AVANT SetupRedirectMiddleware)
app.add_middleware(SetupRedirectMiddleware)
app.add_middleware(AuthMiddleware)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Inclure les routes
app.include_router(setup_router)
app.include_router(auth_router)

# Monter le dossier torrents
if TORRENT_DIR.exists():
    app.mount("/torrents", StaticFiles(directory=str(TORRENT_DIR)), name="torrents")

# ==================== LIFECYCLE ====================

@app.on_event("startup")
async def startup():
    """Au démarrage de l'app"""
    init_db()
    start_scheduler()
    print("✅ Application démarrée v2.6.8")

@app.on_event("shutdown")
async def shutdown():
    """À l'arrêt de l'app"""
    stop_scheduler()
    print("✅ Application arrêtée")

# ==================== HEALTH ====================

@app.get("/health")
async def health():
    """Healthcheck complet avec vérification de tous les composants"""
    import requests
    
    checks = {
        "status": "ok",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "2.8.8",
        "components": {
            "database": "unknown",
            "prowlarr": "unknown",
            "scheduler": "unknown"
        }
    }
    
    # 1. Vérifier la base de données
    try:
        if DB_PATH.exists():
            with get_db() as conn:
                conn.execute("SELECT 1").fetchone()
            checks["components"]["database"] = "ok"
        else:
            checks["components"]["database"] = "missing"
            checks["status"] = "degraded"
    except Exception as e:
        checks["components"]["database"] = f"error: {str(e)}"
        checks["status"] = "degraded"
    
    # 2. Vérifier Prowlarr
    try:
        response = requests.get(
            f"{PROWLARR_URL}/api/v1/health",
            headers={"X-Api-Key": PROWLARR_API_KEY},
            timeout=3
        )
        if response.status_code == 200:
            checks["components"]["prowlarr"] = "ok"
        else:
            checks["components"]["prowlarr"] = f"http_{response.status_code}"
            checks["status"] = "degraded"
    except requests.Timeout:
        checks["components"]["prowlarr"] = "timeout"
        checks["status"] = "degraded"
    except requests.ConnectionError:
        checks["components"]["prowlarr"] = "unreachable"
        checks["status"] = "degraded"
    except Exception as e:
        checks["components"]["prowlarr"] = f"error: {str(e)}"
        checks["status"] = "degraded"
    
    # 3. Vérifier le Scheduler
    try:
        from scheduler import scheduler
        if scheduler.running:
            job = scheduler.get_job("sync_prowlarr")
            if job:
                checks["components"]["scheduler"] = "ok"
                checks["components"]["next_sync"] = job.next_run_time.isoformat() if job.next_run_time else None
            else:
                checks["components"]["scheduler"] = "no_job"
                checks["status"] = "degraded"
        else:
            checks["components"]["scheduler"] = "stopped"
            checks["status"] = "degraded"
    except Exception as e:
        checks["components"]["scheduler"] = f"error: {str(e)}"
        checks["status"] = "degraded"
    
    status_code = 200 if checks["status"] == "ok" else 503
    
    return JSONResponse(checks, status_code=status_code)

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

# ==================== LOGIN PAGE ====================

@app.get("/login", response_class=HTMLResponse)
async def login_page():
    """Page de connexion moderne et responsive"""
    html_content = """<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Connexion - Grabb2RSS</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            background: linear-gradient(135deg, #0f0f0f 0%, #1a1a2e 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            color: #e0e0e0;
        }

        .login-container {
            background: #1a1a1a;
            border: 1px solid #333;
            border-radius: 16px;
            padding: 40px;
            width: 100%;
            max-width: 400px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.5);
            animation: fadeIn 0.5s ease-out;
        }

        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(-20px); }
            to { opacity: 1; transform: translateY(0); }
        }

        .logo {
            text-align: center;
            margin-bottom: 30px;
        }

        .logo h1 {
            color: #1e90ff;
            font-size: 32px;
            margin-bottom: 8px;
        }

        .logo p {
            color: #888;
            font-size: 14px;
        }

        .form-group {
            margin-bottom: 20px;
        }

        .form-group label {
            display: block;
            margin-bottom: 8px;
            color: #1e90ff;
            font-weight: 600;
            font-size: 14px;
        }

        .form-group input {
            width: 100%;
            padding: 12px 16px;
            background: #0f0f0f;
            border: 1px solid #333;
            color: #e0e0e0;
            border-radius: 8px;
            font-size: 14px;
            transition: all 0.3s;
        }

        .form-group input:focus {
            outline: none;
            border-color: #1e90ff;
            box-shadow: 0 0 0 3px rgba(30,144,255,0.1);
        }

        .login-button {
            width: 100%;
            padding: 14px;
            background: #1e90ff;
            color: white;
            border: none;
            border-radius: 8px;
            font-weight: 600;
            font-size: 16px;
            cursor: pointer;
            transition: all 0.3s;
            margin-top: 10px;
        }

        .login-button:hover {
            background: #0066cc;
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(30,144,255,0.3);
        }

        .login-button:active {
            transform: translateY(0);
        }

        .login-button:disabled {
            opacity: 0.5;
            cursor: not-allowed;
            transform: none;
        }

        .error-message {
            background: #ff4444;
            color: white;
            padding: 12px;
            border-radius: 8px;
            margin-bottom: 20px;
            font-size: 14px;
            display: none;
            animation: shake 0.5s;
        }

        @keyframes shake {
            0%, 100% { transform: translateX(0); }
            25% { transform: translateX(-10px); }
            75% { transform: translateX(10px); }
        }

        .footer {
            text-align: center;
            margin-top: 30px;
            color: #888;
            font-size: 12px;
        }

        .loading {
            display: none;
            text-align: center;
            margin-top: 10px;
            color: #1e90ff;
        }

        .loading::after {
            content: '...';
            animation: dots 1.5s steps(4, end) infinite;
        }

        @keyframes dots {
            0%, 20% { content: '.'; }
            40% { content: '..'; }
            60%, 100% { content: '...'; }
        }

        @media (max-width: 480px) {
            .login-container {
                padding: 30px 20px;
                margin: 20px;
            }

            .logo h1 {
                font-size: 28px;
            }
        }
    </style>
</head>
<body>
    <div class="login-container">
        <div class="logo">
            <h1>🔐 Grabb2RSS</h1>
            <p>Connexion Sécurisée</p>
        </div>

        <div id="error-message" class="error-message"></div>

        <form id="login-form">
            <div class="form-group">
                <label for="username">Nom d'utilisateur</label>
                <input type="text" id="username" name="username" required autocomplete="username" autofocus>
            </div>

            <div class="form-group">
                <label for="password">Mot de passe</label>
                <input type="password" id="password" name="password" required autocomplete="current-password">
            </div>

            <button type="submit" class="login-button" id="login-btn">
                Se connecter
            </button>

            <div class="loading" id="loading">Connexion en cours</div>
        </form>

        <div class="footer">
            <p>Grabb2RSS v2.6.8 - Convertisseur Prowlarr → RSS</p>
        </div>
    </div>

    <script>
        const form = document.getElementById('login-form');
        const errorMessage = document.getElementById('error-message');
        const loginBtn = document.getElementById('login-btn');
        const loading = document.getElementById('loading');

        form.addEventListener('submit', async (e) => {
            e.preventDefault();

            // Récupérer les valeurs
            const username = document.getElementById('username').value;
            const password = document.getElementById('password').value;

            // Désactiver le formulaire
            loginBtn.disabled = true;
            loginBtn.textContent = 'Connexion...';
            loading.style.display = 'block';
            errorMessage.style.display = 'none';

            try {
                // Envoyer la requête de connexion
                const response = await fetch('/api/auth/login', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ username, password }),
                    credentials: 'include'
                });

                const data = await response.json();

                if (data.success) {
                    // Connexion réussie - rediriger vers la page d'accueil
                    window.location.href = '/';
                } else {
                    // Afficher l'erreur
                    errorMessage.textContent = data.message || 'Identifiants incorrects';
                    errorMessage.style.display = 'block';
                    loginBtn.disabled = false;
                    loginBtn.textContent = 'Se connecter';
                    loading.style.display = 'none';

                    // Réinitialiser le mot de passe
                    document.getElementById('password').value = '';
                    document.getElementById('password').focus();
                }
            } catch (error) {
                errorMessage.textContent = 'Erreur de connexion au serveur';
                errorMessage.style.display = 'block';
                loginBtn.disabled = false;
                loginBtn.textContent = 'Se connecter';
                loading.style.display = 'none';
                console.error('Erreur:', error);
            }
        });

        // Focus sur le champ username au chargement
        document.getElementById('username').focus();
    </script>
</body>
</html>"""
    return HTMLResponse(content=html_content)

@app.get("/", response_class=HTMLResponse)
async def web_ui():
    """Interface Web complète v2.6.8 - CORRIGÉE"""
    html_content = """<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Grab2RSS v2.6.8 - Dashboard</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@3.9.1/dist/chart.min.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #0f0f0f; color: #e0e0e0; }
        .container { max-width: 1400px; margin: 0 auto; padding: 20px; }
        header { border-bottom: 2px solid #1e90ff; padding-bottom: 20px; margin-bottom: 30px; }
        h1 { font-size: 32px; color: #1e90ff; margin-bottom: 5px; }
        .subtitle { color: #888; font-size: 14px; }
        
        .tabs { display: flex; gap: 0; margin-bottom: 30px; border-bottom: 2px solid #333; overflow-x: auto; }
        .tab-button { background: #1a1a1a; border: none; color: #888; padding: 15px 20px; cursor: pointer; font-weight: 600; border-bottom: 3px solid transparent; transition: 0.3s; white-space: nowrap; }
        .tab-button:hover { color: #1e90ff; }
        .tab-button.active { color: #1e90ff; border-bottom-color: #1e90ff; }
        
        .tab-content { display: none; }
        .tab-content.active { display: block; animation: fadeIn 0.3s; }
        @keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
        
        .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 20px; margin-bottom: 30px; }
        .card { background: #1a1a1a; border: 1px solid #333; border-radius: 8px; padding: 20px; }
        .card h3 { color: #1e90ff; margin-bottom: 10px; font-size: 14px; text-transform: uppercase; }
        .card .value { font-size: 28px; font-weight: bold; color: #fff; }
        .card .unit { font-size: 12px; color: #888; margin-left: 5px; }
        
        .chart-container { background: #1a1a1a; border: 1px solid #333; border-radius: 8px; padding: 20px; margin-bottom: 20px; position: relative; height: 400px; }
        .chart-small { height: 300px; }
        
        table { width: 100%; border-collapse: collapse; margin-top: 20px; }
        th { background: #1e90ff; color: #000; padding: 12px; text-align: left; font-weight: 600; }
        td { padding: 12px; border-bottom: 1px solid #333; }
        tr:hover { background: #1e1e1e; }
        
        .button { background: #1e90ff; color: white; border: none; padding: 10px 15px; border-radius: 4px; cursor: pointer; font-weight: 600; transition: 0.2s; }
        .button:hover { background: #0066cc; }
        .button.danger { background: #ff4444; }
        .button.danger:hover { background: #cc0000; }
        .button.success { background: #00aa00; }
        .button.success:hover { background: #008800; }
        .button:disabled { opacity: 0.5; cursor: not-allowed; }
        
        .actions { margin-top: 20px; display: flex; gap: 10px; flex-wrap: wrap; }
        .status { display: flex; align-items: center; gap: 8px; }
        .status.online::before { content: "●"; color: #00dd00; font-size: 12px; }
        .status.offline::before { content: "●"; color: #ff4444; font-size: 12px; }
        .date { color: #888; font-size: 12px; }
        
        .form-group { margin-bottom: 20px; }
        .form-group label { display: block; margin-bottom: 8px; color: #1e90ff; font-weight: 600; }
        .form-group input, .form-group select { width: 100%; padding: 10px; background: #1a1a1a; border: 1px solid #333; color: #e0e0e0; border-radius: 4px; font-size: 14px; }
        .form-group input:focus, .form-group select:focus { outline: none; border-color: #1e90ff; box-shadow: 0 0 5px rgba(30,144,255,0.3); }
        .form-group small { display: block; margin-top: 5px; color: #888; font-size: 12px; }
        
        .filter-bar { background: #1a1a1a; border: 1px solid #333; border-radius: 8px; padding: 15px; margin-bottom: 20px; display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }
        .filter-bar select { padding: 8px; background: #0f0f0f; border: 1px solid #333; color: #e0e0e0; border-radius: 4px; cursor: pointer; }
        
        .rss-section { background: #1a1a1a; border: 1px solid #333; border-radius: 8px; padding: 20px; margin-bottom: 20px; }
        .rss-section h3 { color: #1e90ff; margin-bottom: 15px; }
        .rss-url { background: #0f0f0f; padding: 10px; border-radius: 4px; margin-bottom: 10px; word-break: break-all; font-family: monospace; font-size: 11px; border: 1px solid #333; }
        .copy-btn { background: #333; color: #1e90ff; border: 1px solid #1e90ff; padding: 5px 10px; border-radius: 4px; cursor: pointer; font-size: 12px; transition: 0.2s; }
        .copy-btn:hover { background: #1e90ff; color: #000; }
        
        .stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; margin-bottom: 20px; }
        
        .alert { padding: 15px; border-radius: 4px; margin-bottom: 15px; }
        .alert.info { background: #003366; color: #1e90ff; border-left: 4px solid #1e90ff; }
        
        .log-item { background: #1a1a1a; border-left: 4px solid #333; padding: 12px; margin-bottom: 10px; border-radius: 4px; }
        .log-item.success { border-left-color: #00aa00; }
        .log-item.error { border-left-color: #ff4444; }
        .log-item.warning { border-left-color: #ffaa00; }
        .log-item.info { border-left-color: #1e90ff; }
        .log-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
        .log-level { font-weight: bold; font-size: 14px; }
        .log-level.success { color: #00aa00; }
        .log-level.error { color: #ff4444; }
        .log-level.warning { color: #ffaa00; }
        .log-level.info { color: #1e90ff; }
        .log-time { color: #888; font-size: 12px; }
        .log-message { margin-bottom: 5px; }
        .log-details { color: #888; font-size: 12px; font-family: monospace; }
        
        h2 { color: #1e90ff; margin: 30px 0 15px 0; }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <div>
                    <h1>📡 Grabb2RSS v2.6.8</h1>
                    <p class="subtitle">Convertisseur Prowlarr → RSS avec Flux Personnalisés + Admin</p>
                </div>
                <div id="auth-info" style="display: none; text-align: right;">
                    <p style="color: #888; font-size: 13px; margin-bottom: 5px;">
                        Connecté en tant que: <span id="username-display" style="color: #1e90ff; font-weight: 600;"></span>
                    </p>
                    <button class="button" onclick="logout()" style="font-size: 13px; padding: 8px 15px;">
                        🚪 Déconnexion
                    </button>
                </div>
            </div>
        </header>

        <div class="tabs">
            <button class="tab-button active" onclick="switchTab('dashboard')">📊 Dashboard</button>
            <button class="tab-button" onclick="switchTab('grabs')">📋 Grabs</button>
            <button class="tab-button" onclick="switchTab('torrents')">📦 Torrents</button>
            <button class="tab-button" onclick="switchTab('stats')">📈 Statistiques</button>
            <button class="tab-button" onclick="switchTab('rss')">📡 Flux RSS</button>
            <button class="tab-button" onclick="switchTab('logs')">📝 Logs</button>
            <button class="tab-button" onclick="switchTab('config')">⚙️ Configuration</button>
            <button class="tab-button" onclick="switchTab('security')" id="security-tab" style="display: none;">🔐 Sécurité</button>
            <button class="tab-button" onclick="switchTab('admin')">🔧 Admin</button>
        </div>

        <!-- TAB: DASHBOARD -->
        <div id="dashboard" class="tab-content active">
            <div class="alert info" style="margin-bottom: 20px;">
                <strong>👋 Bienvenue sur Grab2RSS v2.6.8</strong><br>
                <span style="color: #ddd;">Votre convertisseur Prowlarr → RSS est opérationnel. Surveillez vos grabs, gérez vos torrents et configurez vos flux RSS personnalisés.</span>
            </div>

            <div class="grid">
                <div class="card">
                    <h3>📋 Total Grabs</h3>
                    <div class="value" id="total-grabs">-</div>
                    <p style="color: #888; font-size: 12px; margin-top: 10px;">Grabs enregistrés en base</p>
                </div>
                <div class="card">
                    <h3>📦 Fichiers Torrents</h3>
                    <div class="value" id="dashboard-torrent-count">-</div>
                    <p style="color: #888; font-size: 12px; margin-top: 10px;">
                        Taille: <span id="dashboard-torrent-size">-</span> MB
                    </p>
                </div>
                <div class="card">
                    <h3>💾 Stockage Total</h3>
                    <div class="value"><span id="storage-size">-</span><span class="unit">MB</span></div>
                    <p style="color: #888; font-size: 12px; margin-top: 10px;">Base + Torrents</p>
                </div>
                <div class="card">
                    <h3>📡 Statut Sync</h3>
                    <div class="status" id="sync-status"></div>
                    <div class="date" id="next-sync" style="margin-top: 10px;">-</div>
                </div>
            </div>

            <div class="grid" style="margin-top: 20px;">
                <div class="card">
                    <h3>🕒 Dernier Grab</h3>
                    <div class="value" id="latest-grab" style="font-size: 14px; margin-top: 10px;">-</div>
                </div>
                <div class="card">
                    <h3>🎯 Trackers Actifs</h3>
                    <div class="value" id="dashboard-trackers-count">-</div>
                    <p style="color: #888; font-size: 12px; margin-top: 10px;">Trackers différents</p>
                </div>
                <div class="card">
                    <h3>📊 Grabs Aujourd'hui</h3>
                    <div class="value" id="dashboard-grabs-today">-</div>
                    <p style="color: #888; font-size: 12px; margin-top: 10px;">Dernières 24h</p>
                </div>
                <div class="card">
                    <h3>⏱️ Uptime</h3>
                    <div class="value" id="dashboard-uptime" style="font-size: 20px;">-</div>
                    <p style="color: #888; font-size: 12px; margin-top: 10px;">Temps d'activité</p>
                </div>
            </div>

            <h2>🎯 Actions Rapides</h2>
            <div class="actions">
                <button class="button" onclick="refreshData()">🔄 Actualiser Dashboard</button>
                <button class="button success" id="sync-btn" onclick="syncNow()">📡 Synchroniser Maintenant</button>
                <button class="button" onclick="switchTab('torrents')">📦 Gérer les Torrents</button>
                <button class="button danger" onclick="purgeAllGrabs()">🗑️ Vider Tous les Grabs</button>
            </div>

            <h2 style="margin-top: 30px;">🔗 Accès Rapides</h2>
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin-top: 15px;">
                <a href="/rss" target="_blank" style="background: #1a1a1a; border: 1px solid #333; border-radius: 8px; padding: 15px; text-decoration: none; color: #1e90ff; display: block; transition: 0.2s;">
                    <strong style="display: block; margin-bottom: 5px;">📡 Flux RSS Global</strong>
                    <span style="color: #888; font-size: 12px;">Tous les trackers</span>
                </a>
                <a href="/api/stats" target="_blank" style="background: #1a1a1a; border: 1px solid #333; border-radius: 8px; padding: 15px; text-decoration: none; color: #1e90ff; display: block; transition: 0.2s;">
                    <strong style="display: block; margin-bottom: 5px;">📊 Statistiques API</strong>
                    <span style="color: #888; font-size: 12px;">Format JSON</span>
                </a>
                <a href="/health" target="_blank" style="background: #1a1a1a; border: 1px solid #333; border-radius: 8px; padding: 15px; text-decoration: none; color: #1e90ff; display: block; transition: 0.2s;">
                    <strong style="display: block; margin-bottom: 5px;">💚 Health Check</strong>
                    <span style="color: #888; font-size: 12px;">État des services</span>
                </a>
                <a href="javascript:void(0)" onclick="switchTab('config')" style="background: #1a1a1a; border: 1px solid #333; border-radius: 8px; padding: 15px; text-decoration: none; color: #1e90ff; display: block; transition: 0.2s;">
                    <strong style="display: block; margin-bottom: 5px;">⚙️ Configuration</strong>
                    <span style="color: #888; font-size: 12px;">Modifier les paramètres</span>
                </a>
            </div>
        </div>

        <!-- TAB: GRABS -->
        <div id="grabs" class="tab-content">
            <h2>📋 Derniers Grabs</h2>

            <div class="filter-bar">
                <label for="tracker-filter-grabs" style="margin: 0; color: #1e90ff; font-weight: 600;">Filtrer par Tracker:</label>
                <select id="tracker-filter-grabs" onchange="filterGrabs()" style="flex: 0 0 auto; min-width: 200px;">
                    <option value="all">Tous les trackers</option>
                </select>
            </div>

            <table>
                <thead>
                    <tr>
                        <th>Date</th>
                        <th>Titre</th>
                        <th>Tracker</th>
                        <th>Fichier</th>
                    </tr>
                </thead>
                <tbody id="grabs-table">
                    <tr><td colspan="4" style="text-align: center; color: #888;">Chargement...</td></tr>
                </tbody>
            </table>
        </div>

        <!-- TAB: TORRENTS -->
        <div id="torrents" class="tab-content">
            <h2>📦 Gestion des Fichiers Torrents</h2>
            <p style="color: #888; margin-bottom: 20px;">Gérez vos fichiers torrents : téléchargement, suppression, nettoyage des orphelins</p>

            <div class="grid" style="margin-bottom: 20px;">
                <div class="card">
                    <h3>Total Fichiers</h3>
                    <div class="value" id="torrents-total">-</div>
                </div>
                <div class="card">
                    <h3>Taille Totale</h3>
                    <div class="value"><span id="torrents-size">-</span><span class="unit">MB</span></div>
                </div>
                <div class="card">
                    <h3>Avec Grab</h3>
                    <div class="value" id="torrents-with-grab">-</div>
                </div>
                <div class="card">
                    <h3>Orphelins</h3>
                    <div class="value" id="torrents-orphans" style="color: #ff6b6b;">-</div>
                </div>
            </div>

            <div class="actions" style="margin-bottom: 20px;">
                <button class="button" onclick="loadTorrents()">🔄 Actualiser</button>
                <button class="button" onclick="cleanupOrphanTorrents()">🗑️ Nettoyer Orphelins</button>
                <button class="button danger" onclick="purgeAllTorrents()">🗑️ Vider Tous les Torrents</button>
            </div>

            <table>
                <thead>
                    <tr>
                        <th style="width: 40px;"><input type="checkbox" id="select-all-torrents" onchange="toggleAllTorrents()"></th>
                        <th>Fichier</th>
                        <th>Titre</th>
                        <th>Tracker</th>
                        <th>Date Grab</th>
                        <th>Taille</th>
                        <th>Statut</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody id="torrents-table">
                    <tr><td colspan="8" style="text-align: center; color: #888;">Chargement...</td></tr>
                </tbody>
            </table>

            <div class="actions" style="margin-top: 20px;" id="bulk-actions" style="display: none;">
                <button class="button danger" onclick="deleteBulkTorrents()">🗑️ Supprimer la sélection</button>
            </div>
        </div>

        <!-- TAB: STATISTIQUES -->
        <div id="stats" class="tab-content">
            <h2>📈 Statistiques Détaillées</h2>
            
            <div class="stats-grid">
                <div class="chart-container chart-small">
                    <canvas id="trackerChart"></canvas>
                </div>
                <div class="chart-container chart-small">
                    <canvas id="grabsByDayChart"></canvas>
                </div>
            </div>
            
            <div class="chart-container">
                <canvas id="topTorrentsChart"></canvas>
            </div>
            
            <h3 style="margin-top: 40px; margin-bottom: 15px;">📊 Grabs par Tracker</h3>
            <table id="tracker-stats-table">
                <thead>
                    <tr>
                        <th>Tracker</th>
                        <th>Nombre de grabs</th>
                        <th>Pourcentage</th>
                    </tr>
                </thead>
                <tbody id="tracker-stats-body">
                    <tr><td colspan="3" style="text-align: center; color: #888;">Chargement...</td></tr>
                </tbody>
            </table>
        </div>

        <!-- TAB: RSS FEEDS -->
        <div id="rss" class="tab-content">
            <h2>📡 Flux RSS Personnalisés</h2>
            <p style="color: #888; margin-bottom: 20px;">Copiez l'URL appropriée pour votre client torrent</p>
            
            <div class="rss-section">
                <h3>🎯 Flux Global (Tous les Trackers)</h3>
                <p style="color: #888; font-size: 12px; margin-bottom: 10px;">Compatible rutorrent, qBittorrent, Transmission</p>
                
                <p style="margin-bottom: 10px; color: #ddd;"><strong>Format XML:</strong></p>
                <div class="rss-url" id="rss-global-xml">https://example.com/rss</div>
                <button class="copy-btn" onclick="copyToClipboard('rss-global-xml')">📋 Copier</button>
                
                <p style="margin-top: 15px; margin-bottom: 10px; color: #ddd;"><strong>Format JSON:</strong></p>
                <div class="rss-url" id="rss-global-json">https://example.com/rss/torrent.json</div>
                <button class="copy-btn" onclick="copyToClipboard('rss-global-json')">📋 Copier</button>
            </div>
            
            <div class="rss-section">
                <h3>🔍 Flux par Tracker</h3>
                <p style="color: #888; font-size: 12px; margin-bottom: 15px;">Sélectionnez un tracker pour générer son flux personnalisé</p>
                
                <div class="filter-bar">
                    <label for="tracker-filter-rss" style="margin: 0;">Tracker:</label>
                    <select id="tracker-filter-rss" onchange="updateTrackerRssUrls()" style="flex: 0 0 auto; min-width: 250px;">
                        <option value="all">Tous</option>
                    </select>
                </div>
                
                <p style="margin-bottom: 10px; color: #ddd;"><strong>Format XML:</strong></p>
                <div class="rss-url" id="rss-tracker-xml">-</div>
                <button class="copy-btn" onclick="copyToClipboard('rss-tracker-xml')">📋 Copier</button>
                
                <p style="margin-top: 15px; margin-bottom: 10px; color: #ddd;"><strong>Format JSON:</strong></p>
                <div class="rss-url" id="rss-tracker-json">-</div>
                <button class="copy-btn" onclick="copyToClipboard('rss-tracker-json')">📋 Copier</button>
            </div>
            
            <div class="alert alert-info">
                <strong>💡 Utilisation:</strong> Copiez l'URL dans votre client torrent (rutorrent, qBittorrent, Transmission, etc). Les flux se mettent à jour automatiquement.
            </div>
        </div>

        <!-- TAB: LOGS -->
        <div id="logs" class="tab-content">
            <h2>📝 Historique Synchronisations</h2>
            <table>
                <thead>
                    <tr>
                        <th>Date</th>
                        <th>Statut</th>
                        <th>Grabs</th>
                        <th>Doublons</th>
                        <th>Erreur</th>
                    </tr>
                </thead>
                <tbody id="logs-table">
                    <tr><td colspan="5" style="text-align: center; color: #888;">Chargement...</td></tr>
                </tbody>
            </table>
        </div>

        <!-- TAB: CONFIG -->
        <div id="config" class="tab-content">
            <h2>⚙️ Configuration</h2>
            <div id="config-form"></div>
            <div style="margin-top: 20px;">
                <button class="button success" onclick="saveConfig()">💾 Sauvegarder</button>
                <button class="button" onclick="loadConfig()">🔄 Recharger</button>
            </div>
        </div>

        <!-- TAB: ADMIN (NOUVEAU v2.6.8) -->
        <div id="admin" class="tab-content">
            <h2>🔧 Administration & Maintenance</h2>
            
            <h3 style="margin-top: 20px; margin-bottom: 15px;">📊 Statistiques Système</h3>
            <div class="grid">
                <div class="card">
                    <h3>Base de Données</h3>
                    <div class="value"><span id="admin-db-size">-</span><span class="unit">MB</span></div>
                    <p style="color: #888; font-size: 12px; margin-top: 10px;">
                        Grabs: <span id="admin-db-grabs">-</span> |
                        Logs: <span id="admin-db-logs">-</span>
                    </p>
                </div>
                <div class="card">
                    <h3>Fichiers Torrents</h3>
                    <div class="value"><span id="admin-torrent-count">-</span></div>
                    <p style="color: #888; font-size: 12px; margin-top: 10px;">
                        Taille: <span id="admin-torrent-size">-</span> MB<br>
                        Orphelins: <span id="admin-torrent-orphans" style="color: #ff6b6b;">-</span>
                    </p>
                </div>
                <div class="card">
                    <h3>Mémoire</h3>
                    <div class="value"><span id="admin-memory">-</span><span class="unit">MB</span></div>
                    <p style="color: #888; font-size: 12px; margin-top: 10px;">
                        CPU: <span id="admin-cpu">-</span>%
                    </p>
                </div>
                <div class="card">
                    <h3>Uptime</h3>
                    <div class="value" id="admin-uptime" style="font-size: 20px;">-</div>
                </div>
            </div>
            
            <h3 style="margin-top: 30px; margin-bottom: 15px;">🛠️ Actions de Maintenance</h3>
            <div class="actions">
                <button class="button" onclick="loadAdminStats()">🔄 Rafraîchir Stats</button>
                <button class="button" onclick="clearCache()">🗑️ Vider Cache</button>
                <button class="button" onclick="vacuumDatabase()">🔧 Optimiser BD</button>
                <button class="button success" onclick="syncNow()">📡 Forcer Sync</button>
                <button class="button danger" onclick="purgeOldGrabs()">🗑️ Purger Anciens</button>
                <button class="button" onclick="testHistoryLimits()">📊 Tester Limites Historique</button>
            </div>

            <div class="alert info" style="margin-top: 15px;">
                <strong>💡 Configuration :</strong>
                Vous pouvez modifier la configuration via l'onglet <strong>Configuration</strong>.
                Les paramètres sont sauvegardés dans <strong>/config/settings.yml</strong>.
                Un redémarrage peut être nécessaire pour certains paramètres (SYNC_INTERVAL, etc.).
            </div>
            
            <h3 style="margin-top: 30px; margin-bottom: 15px;">📋 Logs de Synchronisation</h3>
            <div class="filter-bar">
                <label for="log-level-filter" style="margin: 0; color: #1e90ff; font-weight: 600;">Niveau:</label>
                <select id="log-level-filter" onchange="loadSystemLogs()" style="flex: 0 0 auto; min-width: 150px;">
                    <option value="all">Tous</option>
                    <option value="success">Succès</option>
                    <option value="error">Erreurs</option>
                    <option value="warning">Avertissements</option>
                    <option value="info">Informations</option>
                </select>
                <button class="button danger" onclick="purgeAllLogs()" style="margin-left: auto;">🗑️ Vider Tous les Logs</button>
            </div>
            <div id="system-logs-container" style="max-height: 500px; overflow-y: auto; margin-top: 15px;">
                <p style="text-align: center; color: #888; padding: 20px;">Chargement des logs...</p>
            </div>

            <div class="alert info" style="margin-top: 15px;">
                <strong>💡 À propos des logs :</strong>
                Les logs affichent l'historique des synchronisations avec Prowlarr. Chaque log contient le nombre de grabs récupérés, les doublons détectés et les éventuelles erreurs. Vous pouvez supprimer individuellement les logs ou vider tous les logs pour libérer de l'espace.
            </div>

            <h3 style="margin-top: 30px; margin-bottom: 15px;">📊 Test des Limites d'Historique</h3>
            <div id="history-test-results" style="display: none;">
                <div class="alert info" style="margin-bottom: 15px;">
                    <strong>📝 Résultats du test</strong><br>
                    <span id="history-test-timestamp" style="color: #888; font-size: 12px;"></span>
                </div>
                <div style="background: #1a1a1a; padding: 15px; border-radius: 8px; border: 1px solid #333;">
                    <pre id="history-test-content" style="margin: 0; white-space: pre-wrap; font-size: 12px; color: #ddd; max-height: 400px; overflow-y: auto;"></pre>
                </div>
                <div style="margin-top: 10px; text-align: right;">
                    <a id="history-test-download" href="#" download="history_limits_test.json" class="button" style="text-decoration: none;">💾 Télécharger JSON</a>
                </div>
            </div>
        </div>

        <!-- TAB: SÉCURITÉ -->
        <div id="security" class="tab-content">
            <h2>🔐 Sécurité & Authentification</h2>
            <p style="color: #888; margin-bottom: 20px;">Gérez votre compte, votre mot de passe et vos API keys pour l'accès aux flux RSS</p>

            <!-- Section: Compte -->
            <div class="card" style="margin-bottom: 30px;">
                <h3>👤 Mon Compte</h3>
                <div style="margin-top: 15px;">
                    <p style="color: #888; margin-bottom: 10px;">
                        Utilisateur: <strong id="security-username" style="color: #1e90ff;">-</strong>
                    </p>
                    <div class="actions">
                        <button class="button" onclick="showChangePasswordForm()">🔑 Changer le mot de passe</button>
                    </div>
                </div>

                <!-- Formulaire de changement de mot de passe -->
                <div id="change-password-form" style="display: none; margin-top: 20px; padding-top: 20px; border-top: 1px solid #333;">
                    <h4 style="color: #1e90ff; margin-bottom: 15px;">Changer le mot de passe</h4>
                    <div class="form-group">
                        <label>Ancien mot de passe</label>
                        <input type="password" id="old-password" placeholder="Ancien mot de passe">
                    </div>
                    <div class="form-group">
                        <label>Nouveau mot de passe</label>
                        <input type="password" id="new-password" placeholder="Minimum 8 caractères">
                    </div>
                    <div class="actions">
                        <button class="button success" onclick="changePassword()">✅ Confirmer</button>
                        <button class="button" onclick="hideChangePasswordForm()">❌ Annuler</button>
                    </div>
                </div>
            </div>

            <!-- Section: API Keys -->
            <div class="card">
                <h3>🔑 API Keys</h3>
                <p style="color: #888; font-size: 13px; margin-bottom: 15px;">
                    Les API Keys permettent l'accès aux flux RSS depuis l'extérieur du réseau local.
                    Ajoutez <code style="background: #0f0f0f; padding: 2px 6px; border-radius: 3px;">?api_key=VOTRE_CLE</code> à l'URL du flux RSS.
                </p>

                <!-- Création d'API Key -->
                <div style="background: #0f0f0f; border: 1px solid #333; border-radius: 8px; padding: 15px; margin-bottom: 20px;">
                    <h4 style="color: #1e90ff; margin-bottom: 10px;">Créer une nouvelle API Key</h4>
                    <div class="form-group" style="margin-bottom: 10px;">
                        <input type="text" id="api-key-name" placeholder="Nom de l'API Key (ex: qBittorrent)" style="width: 100%;">
                    </div>
                    <button class="button success" onclick="createApiKey()">➕ Créer</button>
                </div>

                <!-- Liste des API Keys -->
                <div id="api-keys-list">
                    <p style="color: #888; text-align: center;">Chargement...</p>
                </div>
            </div>
        </div>
    </div>

    <script>
        const API_BASE = "/api";
        let configData = {};
        let statsData = {};
        let allTrackers = [];
        let trackerChartInstance = null;
        let grabsByDayChartInstance = null;
        let topTorrentsChartInstance = null;

        function getRssBaseUrl() {
            return window.location.origin;
        }

        function switchTab(tab) {
            // Remove active class from all tabs and buttons
            document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
            document.querySelectorAll('.tab-button').forEach(el => el.classList.remove('active'));

            // Add active class to selected tab
            const tabElement = document.getElementById(tab);
            if (tabElement) {
                tabElement.classList.add('active');
            }

            // Find and activate the corresponding button by searching for onclick with the tab name
            const buttons = document.querySelectorAll('.tab-button');
            buttons.forEach(btn => {
                const onclick = btn.getAttribute('onclick');
                if (onclick && onclick.includes(`'${tab}'`)) {
                    btn.classList.add('active');
                }
            });

            // Load tab content
            if (tab === 'config') loadConfig();
            if (tab === 'logs') loadLogs();
            if (tab === 'grabs') loadGrabs();
            if (tab === 'torrents') loadTorrents();
            if (tab === 'stats') loadStats();
            if (tab === 'rss') loadRssUrls();
            if (tab === 'admin') loadAdminTab();
            if (tab === 'security') loadApiKeys();
        }

        function loadRssUrls() {
            const baseUrl = getRssBaseUrl();
            document.getElementById('rss-global-xml').textContent = baseUrl + '/rss';
            document.getElementById('rss-global-json').textContent = baseUrl + '/rss/torrent.json';
            updateTrackerRssUrls();
        }

        function updateTrackerRssUrls() {
            const tracker = document.getElementById('tracker-filter-rss').value;
            const baseUrl = getRssBaseUrl();
            
            if (tracker === 'all') {
                document.getElementById('rss-tracker-xml').textContent = baseUrl + '/rss';
                document.getElementById('rss-tracker-json').textContent = baseUrl + '/rss/torrent.json';
            } else {
                document.getElementById('rss-tracker-xml').textContent = baseUrl + '/rss/tracker/' + encodeURIComponent(tracker);
                document.getElementById('rss-tracker-json').textContent = baseUrl + '/rss/tracker/' + encodeURIComponent(tracker) + '/json';
            }
        }

        function copyToClipboard(elementId) {
            const text = document.getElementById(elementId).textContent;
            navigator.clipboard.writeText(text).then(() => {
                alert('✅ Copié dans le presse-papiers!');
            }).catch(() => {
                alert('❌ Erreur lors de la copie');
            });
        }

        async function loadTrackers() {
            try {
                const res = await fetch(API_BASE + '/trackers');
                if (!res.ok) throw new Error('Trackers API error: ' + res.status);
                
                const data = await res.json();
                allTrackers = data.trackers;
                
                [document.getElementById('tracker-filter-grabs'), document.getElementById('tracker-filter-rss')].forEach(select => {
                    if (!select) return;
                    select.innerHTML = '<option value="all">Tous les trackers</option>';
                    allTrackers.forEach(tracker => {
                        const option = document.createElement('option');
                        option.value = tracker;
                        option.textContent = tracker;
                        select.appendChild(option);
                    });
                });
            } catch (e) {
                console.error("❌ Erreur loadTrackers:", e);
            }
        }

        async function filterGrabs() {
            const tracker = document.getElementById('tracker-filter-grabs').value;
            const url = API_BASE + '/grabs?limit=100&tracker=' + encodeURIComponent(tracker);
            
            try {
                const grabs = await fetch(url).then(r => r.json());
                const tbody = document.getElementById("grabs-table");
                tbody.innerHTML = grabs.length ? grabs.map(g => 
                    '<tr>' +
                    '<td class="date">' + new Date(g.grabbed_at).toLocaleString('fr-FR') + '</td>' +
                    '<td>' + g.title + '</td>' +
                    '<td><strong style="color: #1e90ff;">' + (g.tracker || 'N/A') + '</strong></td>' +
                    '<td><a href="/torrents/' + encodeURIComponent(g.torrent_file) + '" target="_blank" style="color: #1e90ff; text-decoration: none;">📥 Download</a></td>' +
                    '</tr>'
                ).join("") : '<tr><td colspan="4" style="text-align: center; color: #888;">Aucun grab</td></tr>';
            } catch (e) {
                console.error("Erreur filterGrabs:", e);
            }
        }

        async function loadStats() {
            try {
                const res = await fetch(API_BASE + '/stats');
                statsData = await res.json();
                
                const trackerLabels = statsData.tracker_stats.map(t => t.tracker);
                const trackerData = statsData.tracker_stats.map(t => t.count);
                
                const trackerCtx = document.getElementById('trackerChart').getContext('2d');
                if (trackerChartInstance) trackerChartInstance.destroy();
                trackerChartInstance = new Chart(trackerCtx, {
                    type: 'doughnut',
                    data: {
                        labels: trackerLabels,
                        datasets: [{
                            data: trackerData,
                            backgroundColor: [
                                '#1e90ff', '#ff6b6b', '#4ecdc4', '#45b7d1', '#f7b731',
                                '#5f27cd', '#00d2d3', '#ff9ff3', '#54a0ff', '#48dbfb'
                            ]
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {
                            legend: { labels: { color: '#e0e0e0' } },
                            title: { display: true, text: 'Grabs par Tracker', color: '#1e90ff' }
                        }
                    }
                });
                
                const dayLabels = statsData.grabs_by_day.map(d => d.day).reverse();
                const dayData = statsData.grabs_by_day.map(d => d.count).reverse();
                
                const dayCtx = document.getElementById('grabsByDayChart').getContext('2d');
                if (grabsByDayChartInstance) grabsByDayChartInstance.destroy();
                grabsByDayChartInstance = new Chart(dayCtx, {
                    type: 'line',
                    data: {
                        labels: dayLabels,
                        datasets: [{
                            label: 'Grabs',
                            data: dayData,
                            borderColor: '#1e90ff',
                            backgroundColor: 'rgba(30, 144, 255, 0.1)',
                            tension: 0.4,
                            fill: true
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {
                            legend: { labels: { color: '#e0e0e0' } },
                            title: { display: true, text: 'Grabs par Jour (30 derniers jours)', color: '#1e90ff' }
                        },
                        scales: {
                            y: { ticks: { color: '#e0e0e0' }, grid: { color: '#333' } },
                            x: { ticks: { color: '#e0e0e0' }, grid: { color: '#333' } }
                        }
                    }
                });
                
                const topLabels = statsData.top_torrents.map(t => t.title.substring(0, 30) + '...');
                const topData = Array(statsData.top_torrents.length).fill(1);
                
                const topCtx = document.getElementById('topTorrentsChart').getContext('2d');
                if (topTorrentsChartInstance) topTorrentsChartInstance.destroy();
                topTorrentsChartInstance = new Chart(topCtx, {
                    type: 'bar',
                    data: {
                        labels: topLabels,
                        datasets: [{
                            label: 'Top Torrents',
                            data: topData,
                            backgroundColor: '#1e90ff'
                        }]
                    },
                    options: {
                        indexAxis: 'y',
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {
                            legend: { labels: { color: '#e0e0e0' } },
                            title: { display: true, text: 'Top 10 des Torrents Récents', color: '#1e90ff' }
                        },
                        scales: {
                            y: { ticks: { color: '#e0e0e0' }, grid: { color: '#333' } },
                            x: { ticks: { color: '#e0e0e0' }, grid: { color: '#333' } }
                        }
                    }
                });
                
                const total = statsData.tracker_stats.reduce((a, b) => a + b.count, 0);
                let tbody = document.getElementById('tracker-stats-body');
                tbody.innerHTML = statsData.tracker_stats.map(t => 
                    '<tr>' +
                    '<td><strong>' + t.tracker + '</strong></td>' +
                    '<td>' + t.count + '</td>' +
                    '<td>' + ((t.count / total) * 100).toFixed(1) + '%</td>' +
                    '</tr>'
                ).join("");
                
            } catch (e) {
                console.error("Erreur loadStats:", e);
            }
        }

        async function refreshData() {
            try {
                const [stats, sync, detailedStats, torrentsData] = await Promise.all([
                    fetch(API_BASE + '/stats').then(r => r.json()),
                    fetch(API_BASE + '/sync/status').then(r => r.json()),
                    fetch(API_BASE + '/stats/detailed').then(r => r.json()),
                    fetch(API_BASE + '/torrents').then(r => r.json())
                ]);

                // Statistiques principales
                document.getElementById("total-grabs").textContent = stats.total_grabs;
                document.getElementById("storage-size").textContent = stats.storage_size_mb;
                document.getElementById("latest-grab").textContent = stats.latest_grab ? new Date(stats.latest_grab).toLocaleString('fr-FR') : "-";

                // Nouvelles statistiques dashboard
                document.getElementById("dashboard-torrent-count").textContent = torrentsData.total;
                const totalSize = torrentsData.torrents.reduce((acc, t) => acc + t.size_mb, 0);
                document.getElementById("dashboard-torrent-size").textContent = totalSize.toFixed(2);

                // Nombre de trackers différents
                const uniqueTrackers = new Set(stats.tracker_stats.map(t => t.tracker)).size;
                document.getElementById("dashboard-trackers-count").textContent = uniqueTrackers;

                // Grabs aujourd'hui (dernières 24h)
                const yesterday = new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString();
                const grabsToday = stats.grabs_by_day[0]?.count || 0;
                document.getElementById("dashboard-grabs-today").textContent = grabsToday;

                // Uptime
                const uptime = detailedStats.system.uptime_seconds;
                const hours = Math.floor(uptime / 3600);
                const minutes = Math.floor((uptime % 3600) / 60);
                document.getElementById("dashboard-uptime").textContent = hours + 'h ' + minutes + 'm';

                // Statut sync
                const statusEl = document.getElementById("sync-status");

                let statusClass = "status offline";
                let statusText = "Inactif";

                if (sync.is_running) {
                    statusClass = "status online";
                    statusText = "Sync en cours...";
                } else if (sync.next_sync) {
                    statusClass = "status online";
                    statusText = "Actif";
                } else if (sync.last_sync) {
                    statusClass = "status offline";
                    statusText = "Arrêté";
                } else {
                    statusClass = "status offline";
                    statusText = "En attente";
                }

                statusEl.className = statusClass;
                statusEl.textContent = statusText;

                document.getElementById("next-sync").textContent = sync.next_sync ? 'Prochain: ' + new Date(sync.next_sync).toLocaleString('fr-FR') : "-";
            } catch (e) {
                console.error("❌ Erreur refreshData:", e);
            }
        }

        async function loadGrabs() {
            await filterGrabs();
        }

        async function loadLogs() {
            try {
                const logs = await fetch(API_BASE + '/sync/logs?limit=50').then(r => r.json());
                const tbody = document.getElementById("logs-table");
                tbody.innerHTML = logs.length ? logs.map(l => 
                    '<tr>' +
                    '<td class="date">' + new Date(l.sync_at).toLocaleString('fr-FR') + '</td>' +
                    '<td><span class="status ' + (l.status === 'success' ? 'online' : 'offline') + '">' + l.status + '</span></td>' +
                    '<td>' + l.grabs_count + '</td>' +
                    '<td>' + (l.deduplicated_count || 0) + '</td>' +
                    '<td style="color: #ff4444; font-size: 12px;">' + (l.error ? l.error.substring(0, 50) : '-') + '</td>' +
                    '</tr>'
                ).join("") : '<tr><td colspan="5" style="text-align: center; color: #888;">Aucun log</td></tr>';
            } catch (e) {
                console.error("Erreur loadLogs:", e);
            }
        }

        async function loadConfig() {
            try {
                const response = await fetch(API_BASE + '/config');
                configData = await response.json();
                
                const form = document.getElementById("config-form");
                form.innerHTML = Object.entries(configData).map(([key, data]) => 
                    '<div class="form-group">' +
                    '<label for="' + key + '">' + key + '</label>' +
                    '<input type="text" id="' + key + '" name="' + key + '" value="' + (data.value || '') + '" placeholder="' + data.description + '">' +
                    '<small>' + data.description + '</small>' +
                    '</div>'
                ).join("");
            } catch (e) {
                alert("Erreur lors du chargement de la config: " + e);
            }
        }

        async function saveConfig() {
            try {
                const updates = {};
                Object.keys(configData).forEach(key => {
                    const input = document.getElementById(key);
                    if (input) {
                        updates[key] = {
                            value: input.value,
                            description: configData[key]?.description || ""
                        };
                    }
                });
                
                const res = await fetch(API_BASE + '/config', {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(updates)
                });
                
                if (res.ok) {
                    alert("✅ Configuration sauvegardée!");
                    loadConfig();
                } else {
                    alert("❌ Erreur lors de la sauvegarde");
                }
            } catch (e) {
                alert("❌ Erreur: " + e);
            }
        }

        async function syncNow() {
            const btn = document.getElementById("sync-btn");
            btn.disabled = true;
            btn.textContent = "⏳ Sync en cours...";
            
            try {
                const triggerRes = await fetch(API_BASE + '/sync/trigger', { method: "POST" });
                const triggerData = await triggerRes.json();
                
                if (triggerData.status === "already_running") {
                    alert("⏳ Une synchronisation est déjà en cours");
                    btn.disabled = false;
                    btn.textContent = "📡 Sync Maintenant";
                    return;
                }
                
                let syncCompleted = false;
                const maxAttempts = 30;
                
                for (let i = 0; i < maxAttempts; i++) {
                    await new Promise(resolve => setTimeout(resolve, 1000));
                    
                    const statusRes = await fetch(API_BASE + '/sync/status');
                    const status = await statusRes.json();
                    
                    if (!status.is_running) {
                        syncCompleted = true;
                        
                        if (status.last_error) {
                            alert("❌ Erreur sync: " + status.last_error);
                        } else {
                            alert("✅ Synchronisation terminée !");
                        }
                        break;
                    }
                }
                
                if (!syncCompleted) {
                    alert("⏳ La synchronisation prend plus de temps que prévu. Vérifiez les logs.");
                }
                
                await refreshData();
                
            } catch (e) {
                alert("❌ Erreur: " + e);
            } finally {
                btn.disabled = false;
                btn.textContent = "📡 Sync Maintenant";
            }
        }

        async function purgeAllGrabs() {
            if (confirm("⚠️  Êtes-vous CERTAIN ? Cela supprimera TOUS les grabs !")) {
                try {
                    const res = await fetch(API_BASE + '/purge/all', { method: "POST" });
                    const data = await res.json();
                    alert("✅ " + data.message);
                    refreshData();
                    loadGrabs();
                } catch (e) {
                    alert("❌ Erreur: " + e);
                }
            }
        }

        async function loadAdminTab() {
            await loadAdminStats();
            await loadSystemLogs();
        }

        async function loadAdminStats() {
            try {
                const [detailedStats, torrentsData] = await Promise.all([
                    fetch(API_BASE + '/stats/detailed').then(r => r.json()),
                    fetch(API_BASE + '/torrents').then(r => r.json())
                ]);

                document.getElementById('admin-db-size').textContent = detailedStats.database.size_mb;
                document.getElementById('admin-db-grabs').textContent = detailedStats.database.grabs;
                document.getElementById('admin-db-logs').textContent = detailedStats.database.sync_logs;

                document.getElementById('admin-torrent-count').textContent = torrentsData.total;
                const totalSize = torrentsData.torrents.reduce((acc, t) => acc + t.size_mb, 0);
                document.getElementById('admin-torrent-size').textContent = totalSize.toFixed(2);

                // Compter les orphelins
                const orphans = torrentsData.torrents.filter(t => !t.has_grab).length;
                document.getElementById('admin-torrent-orphans').textContent = orphans;

                document.getElementById('admin-memory').textContent = detailedStats.system.memory_mb;
                document.getElementById('admin-cpu').textContent = detailedStats.system.cpu_percent;

                const uptime = detailedStats.system.uptime_seconds;
                const hours = Math.floor(uptime / 3600);
                const minutes = Math.floor((uptime % 3600) / 60);
                document.getElementById('admin-uptime').textContent = hours + 'h ' + minutes + 'm';

            } catch (e) {
                console.error("Erreur loadAdminStats:", e);
                alert("❌ Erreur lors du chargement des stats: " + e);
            }
        }

        async function loadSystemLogs() {
            const level = document.getElementById('log-level-filter').value;

            try {
                // Récupérer tous les logs de sync
                const res = await fetch(API_BASE + '/sync/logs?limit=100');
                const logs = await res.json();

                const container = document.getElementById('system-logs-container');

                if (logs.length === 0) {
                    container.innerHTML = '<p style="text-align: center; color: #888; padding: 20px;">Aucun log trouvé</p>';
                    return;
                }

                // Filtrer par niveau
                let filteredLogs = logs;
                if (level === 'success') {
                    filteredLogs = logs.filter(l => l.status === 'success');
                } else if (level === 'error') {
                    filteredLogs = logs.filter(l => l.status !== 'success');
                }

                if (filteredLogs.length === 0) {
                    container.innerHTML = '<p style="text-align: center; color: #888; padding: 20px;">Aucun log trouvé pour ce niveau</p>';
                    return;
                }

                const logIcons = {
                    'success': '✅',
                    'error': '❌'
                };

                container.innerHTML = filteredLogs.map(log => {
                    const logLevel = log.status === 'success' ? 'success' : 'error';
                    const icon = logIcons[logLevel] || '•';
                    const timestamp = new Date(log.sync_at).toLocaleString('fr-FR');
                    const message = `Sync: ${log.grabs_count} grabs récupérés, ${log.deduplicated_count || 0} doublons ignorés`;
                    const details = log.error ? `Erreur: ${log.error}` : '';

                    return `
                        <div class="log-item ${logLevel}" style="position: relative;">
                            <div class="log-header">
                                <span class="log-level ${logLevel}">
                                    ${icon} ${logLevel.toUpperCase()}
                                </span>
                                <span class="log-time">${timestamp}</span>
                            </div>
                            <div class="log-message">${message}</div>
                            ${details ? '<div class="log-details">' + details + '</div>' : ''}
                        </div>
                    `;
                }).join('');

            } catch (e) {
                console.error("Erreur loadSystemLogs:", e);
                alert("❌ Erreur lors du chargement des logs: " + e);
            }
        }

        async function clearCache() {
            if (confirm("Vider tous les caches (trackers + imports Radarr/Sonarr) ?")) {
                try {
                    const res = await fetch(API_BASE + '/cache/clear', { method: "POST" });
                    const data = await res.json();
                    alert("✅ " + data.message);
                    await loadAdminStats();
                } catch (e) {
                    alert("❌ Erreur: " + e);
                }
            }
        }

        async function vacuumDatabase() {
            if (confirm("Optimiser la base de données (VACUUM) ? Cela peut prendre quelques secondes.")) {
                try {
                    const res = await fetch(API_BASE + '/db/vacuum', { method: "POST" });
                    const data = await res.json();
                    alert("✅ " + data.message + "\\nEspace libéré: " + data.saved_mb + " MB");
                    await loadAdminStats();
                } catch (e) {
                    alert("❌ Erreur: " + e);
                }
            }
        }

        async function purgeOldGrabs() {
            const hours = prompt("Supprimer les grabs plus anciens que combien d'heures ?\\n(168 = 7 jours, 336 = 14 jours, 720 = 30 jours)", "168");

            if (hours === null) return;

            const hoursInt = parseInt(hours);
            if (isNaN(hoursInt) || hoursInt < 1) {
                alert("❌ Valeur invalide");
                return;
            }

            if (confirm("Supprimer tous les grabs > " + hoursInt + "h ?")) {
                try {
                    const res = await fetch(API_BASE + '/purge/retention?hours=' + hoursInt, { method: "POST" });
                    const data = await res.json();
                    alert("✅ " + data.message);
                    await refreshData();
                    await loadAdminStats();
                } catch (e) {
                    alert("❌ Erreur: " + e);
                }
            }
        }

        async function loadTorrents() {
            try {
                const res = await fetch(API_BASE + '/torrents');
                const data = await res.json();

                // Mettre à jour les statistiques
                document.getElementById('torrents-total').textContent = data.total;

                const totalSize = data.torrents.reduce((acc, t) => acc + t.size_mb, 0);
                document.getElementById('torrents-size').textContent = totalSize.toFixed(2);

                const withGrab = data.torrents.filter(t => t.has_grab).length;
                document.getElementById('torrents-with-grab').textContent = withGrab;

                const orphans = data.torrents.filter(t => !t.has_grab).length;
                document.getElementById('torrents-orphans').textContent = orphans;

                // Remplir le tableau
                const tbody = document.getElementById('torrents-table');
                if (data.torrents.length === 0) {
                    tbody.innerHTML = '<tr><td colspan="8" style="text-align: center; color: #888;">Aucun fichier torrent</td></tr>';
                    return;
                }

                tbody.innerHTML = data.torrents.map(t => {
                    const statusColor = t.has_grab ? '#00aa00' : '#ff6b6b';
                    const statusText = t.has_grab ? '✓ Avec Grab' : '⚠ Orphelin';
                    const grabDate = t.grabbed_at ? new Date(t.grabbed_at).toLocaleString('fr-FR') : '-';

                    return `
                        <tr>
                            <td><input type="checkbox" class="torrent-checkbox" value="${t.filename}"></td>
                            <td style="font-family: monospace; font-size: 11px; word-break: break-all;">${t.filename}</td>
                            <td>${t.title}</td>
                            <td><strong style="color: #1e90ff;">${t.tracker}</strong></td>
                            <td class="date">${grabDate}</td>
                            <td>${t.size_mb} MB</td>
                            <td><span style="color: ${statusColor}; font-weight: bold;">${statusText}</span></td>
                            <td>
                                <a href="/torrents/${encodeURIComponent(t.filename)}" target="_blank" class="button" style="text-decoration: none; padding: 5px 10px; font-size: 12px; display: inline-block;">📥 DL</a>
                                <button class="button danger" onclick="deleteSingleTorrent('${t.filename}')" style="padding: 5px 10px; font-size: 12px; margin-left: 5px;">🗑️</button>
                            </td>
                        </tr>
                    `;
                }).join('');

                // Gérer l'affichage du bouton d'actions groupées
                updateBulkActionsVisibility();

            } catch (e) {
                console.error("Erreur loadTorrents:", e);
                alert("❌ Erreur lors du chargement des torrents: " + e);
            }
        }

        function toggleAllTorrents() {
            const selectAll = document.getElementById('select-all-torrents');
            const checkboxes = document.querySelectorAll('.torrent-checkbox');
            checkboxes.forEach(cb => cb.checked = selectAll.checked);
            updateBulkActionsVisibility();
        }

        function updateBulkActionsVisibility() {
            const checkboxes = document.querySelectorAll('.torrent-checkbox:checked');
            const bulkActions = document.getElementById('bulk-actions');
            if (checkboxes.length > 0) {
                bulkActions.style.display = 'flex';
            } else {
                bulkActions.style.display = 'none';
            }
        }

        // Écouter les changements sur les checkboxes
        document.addEventListener('change', (e) => {
            if (e.target.classList.contains('torrent-checkbox')) {
                updateBulkActionsVisibility();
            }
        });

        async function deleteSingleTorrent(filename) {
            if (!confirm(`Supprimer le torrent "${filename}" ?`)) return;

            try {
                const res = await fetch(API_BASE + '/torrents/' + encodeURIComponent(filename), {
                    method: 'DELETE'
                });

                if (res.ok) {
                    alert('✅ Torrent supprimé');
                    await loadTorrents();
                } else {
                    alert('❌ Erreur lors de la suppression');
                }
            } catch (e) {
                alert('❌ Erreur: ' + e);
            }
        }

        async function deleteBulkTorrents() {
            const checkboxes = document.querySelectorAll('.torrent-checkbox:checked');
            const filenames = Array.from(checkboxes).map(cb => cb.value);

            if (filenames.length === 0) {
                alert('⚠️ Aucun torrent sélectionné');
                return;
            }

            if (!confirm(`Supprimer ${filenames.length} torrent(s) sélectionné(s) ?`)) return;

            try {
                let successCount = 0;
                let errorCount = 0;

                for (const filename of filenames) {
                    try {
                        const res = await fetch(API_BASE + '/torrents/' + encodeURIComponent(filename), {
                            method: 'DELETE'
                        });
                        if (res.ok) successCount++;
                        else errorCount++;
                    } catch (e) {
                        errorCount++;
                    }
                }

                alert(`✅ ${successCount} torrent(s) supprimé(s)${errorCount > 0 ? ', ' + errorCount + ' erreur(s)' : ''}`);
                await loadTorrents();

            } catch (e) {
                alert('❌ Erreur: ' + e);
            }
        }

        async function cleanupOrphanTorrents() {
            if (!confirm('Supprimer tous les torrents orphelins (sans grab associé) ?')) return;

            try {
                const res = await fetch(API_BASE + '/torrents/cleanup-orphans', { method: 'POST' });
                const data = await res.json();
                alert('✅ ' + data.message);
                await loadTorrents();
            } catch (e) {
                alert('❌ Erreur: ' + e);
            }
        }

        async function purgeAllTorrents() {
            if (!confirm('⚠️ ATTENTION : Supprimer TOUS les fichiers torrents ? Cette action est irréversible !')) return;

            try {
                const res = await fetch(API_BASE + '/torrents/purge-all', { method: 'POST' });
                const data = await res.json();
                alert('✅ ' + data.message);
                await loadTorrents();
                await loadAdminStats(); // Rafraîchir les stats admin
            } catch (e) {
                alert('❌ Erreur: ' + e);
            }
        }

        async function purgeAllLogs() {
            if (!confirm('Supprimer tous les logs de synchronisation ?')) return;

            try {
                const res = await fetch(API_BASE + '/logs/purge-all', { method: 'POST' });
                const data = await res.json();
                alert('✅ ' + data.message);
                await loadSystemLogs();
            } catch (e) {
                alert('❌ Erreur: ' + e);
            }
        }

        async function testHistoryLimits() {
            const btn = event.target;
            const originalText = btn.textContent;
            btn.disabled = true;
            btn.textContent = "⏳ Test en cours...";

            try {
                const res = await fetch(API_BASE + '/test-history-limits', { method: "POST" });

                if (!res.ok) {
                    throw new Error("Erreur HTTP " + res.status);
                }

                const data = await res.json();

                // Afficher les résultats
                const resultsDiv = document.getElementById('history-test-results');
                resultsDiv.style.display = 'block';

                // Timestamp
                const timestamp = new Date(data.results.timestamp).toLocaleString('fr-FR');
                document.getElementById('history-test-timestamp').textContent =
                    "Test effectué le " + timestamp;

                // Formater les résultats de manière lisible
                const results = data.results;
                let output = "=".repeat(80) + "\\n";
                output += "TEST DES LIMITES D'HISTORIQUE\\n";
                output += "=".repeat(80) + "\\n\\n";

                // Configuration
                output += "📋 CONFIGURATION\\n";
                output += "-".repeat(80) + "\\n";
                output += "Prowlarr URL:      " + results.configuration.prowlarr_url + "\\n";
                output += "Prowlarr pageSize: " + results.configuration.prowlarr_page_size + "\\n";
                output += "Radarr activé:     " + results.configuration.radarr_enabled + "\\n";
                output += "Sonarr activé:     " + results.configuration.sonarr_enabled + "\\n";
                output += "Sync interval:     " + results.configuration.sync_interval_seconds + "s\\n";
                output += "Rétention:         " + results.configuration.retention_hours + "h\\n\\n";

                // Prowlarr
                output += "📡 PROWLARR\\n";
                output += "-".repeat(80) + "\\n";
                results.prowlarr.tested_page_sizes.forEach(test => {
                    const d = test.data;
                    if (d.error) {
                        output += "pageSize=" + test.page_size + " → ❌ " + d.error + "\\n";
                    } else {
                        output += "pageSize=" + test.page_size + " → ";
                        output += d.total + " enregistrements, ";
                        output += d.successful_grabs + " grabs réussis\\n";
                        if (d.oldest_grab) {
                            output += "  Plus ancien: " + new Date(d.oldest_grab).toLocaleString('fr-FR') + "\\n";
                        }
                    }
                });

                output += "\\n🔍 ANALYSE\\n";
                output += "-".repeat(80) + "\\n";
                output += "Type de limitation: " + results.prowlarr.analysis.limitation_type + "\\n";
                output += results.prowlarr.analysis.details + "\\n";
                output += "\\n💡 Recommandation:\\n";
                output += results.prowlarr.analysis.recommendation + "\\n\\n";

                // Radarr
                output += "🎬 RADARR\\n";
                output += "-".repeat(80) + "\\n";
                if (results.radarr.error) {
                    output += "⚠️  " + results.radarr.error + "\\n\\n";
                } else {
                    output += "Total: " + results.radarr.total + " | Grabs: " + results.radarr.grabs + "\\n";
                    if (results.radarr.oldest_grab) {
                        output += "Plus ancien: " + new Date(results.radarr.oldest_grab).toLocaleString('fr-FR') + "\\n";
                    }
                    output += "\\n";
                }

                // Sonarr
                output += "📺 SONARR\\n";
                output += "-".repeat(80) + "\\n";
                if (results.sonarr.error) {
                    output += "⚠️  " + results.sonarr.error + "\\n\\n";
                } else {
                    output += "Total: " + results.sonarr.total + " | Grabs: " + results.sonarr.grabs + "\\n";
                    if (results.sonarr.oldest_grab) {
                        output += "Plus ancien: " + new Date(results.sonarr.oldest_grab).toLocaleString('fr-FR') + "\\n";
                    }
                    output += "\\n";
                }

                // Comparaison
                output += "🔄 COMPARAISON DES PÉRIODES\\n";
                output += "-".repeat(80) + "\\n";
                if (results.comparison.prowlarr_oldest) {
                    output += "Prowlarr: " + new Date(results.comparison.prowlarr_oldest).toLocaleString('fr-FR') + "\\n";
                }
                if (results.comparison.radarr_oldest) {
                    output += "Radarr:   " + new Date(results.comparison.radarr_oldest).toLocaleString('fr-FR') + "\\n";
                }
                if (results.comparison.sonarr_oldest) {
                    output += "Sonarr:   " + new Date(results.comparison.sonarr_oldest).toLocaleString('fr-FR') + "\\n";
                }

                document.getElementById('history-test-content').textContent = output;

                // Lien de téléchargement
                const blob = new Blob([JSON.stringify(results, null, 2)], { type: 'application/json' });
                const url = URL.createObjectURL(blob);
                document.getElementById('history-test-download').href = url;

                // Scroll vers les résultats
                resultsDiv.scrollIntoView({ behavior: 'smooth', block: 'start' });

                alert("✅ Test terminé !\\n\\nRésultats sauvegardés dans:\\n" + data.output_file);

            } catch (e) {
                console.error("Erreur testHistoryLimits:", e);
                alert("❌ Erreur lors du test: " + e);
            } finally {
                btn.disabled = false;
                btn.textContent = originalText;
            }
        }

        // ==================== AUTH & SECURITY ====================

        async function checkAuthStatus() {
            try {
                const res = await fetch('/api/auth/status');
                const data = await res.json();

                if (data.enabled) {
                    // Auth activée - afficher les éléments d'auth
                    document.getElementById('security-tab').style.display = 'block';
                    document.getElementById('auth-info').style.display = 'block';
                    document.getElementById('username-display').textContent = data.username || 'Utilisateur';
                    document.getElementById('security-username').textContent = data.username || 'Utilisateur';
                }
            } catch (error) {
                console.error("Erreur vérification auth:", error);
            }
        }

        async function logout() {
            if (!confirm('Êtes-vous sûr de vouloir vous déconnecter ?')) {
                return;
            }

            try {
                const res = await fetch('/api/auth/logout', { method: 'POST' });
                if (res.ok) {
                    window.location.href = '/login';
                }
            } catch (error) {
                alert('Erreur lors de la déconnexion');
                console.error(error);
            }
        }

        function showChangePasswordForm() {
            document.getElementById('change-password-form').style.display = 'block';
        }

        function hideChangePasswordForm() {
            document.getElementById('change-password-form').style.display = 'none';
            document.getElementById('old-password').value = '';
            document.getElementById('new-password').value = '';
        }

        async function changePassword() {
            const oldPassword = document.getElementById('old-password').value;
            const newPassword = document.getElementById('new-password').value;

            if (!oldPassword || !newPassword) {
                alert('Veuillez remplir tous les champs');
                return;
            }

            if (newPassword.length < 8) {
                alert('Le nouveau mot de passe doit contenir au moins 8 caractères');
                return;
            }

            try {
                const res = await fetch('/api/auth/change-password', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ old_password: oldPassword, new_password: newPassword })
                });

                const data = await res.json();

                if (data.success) {
                    alert('✅ Mot de passe changé avec succès');
                    hideChangePasswordForm();
                } else {
                    alert('❌ Erreur: ' + (data.detail || 'Ancien mot de passe incorrect'));
                }
            } catch (error) {
                alert('❌ Erreur lors du changement de mot de passe');
                console.error(error);
            }
        }

        async function loadApiKeys() {
            try {
                const res = await fetch('/api/auth/api-keys');
                const data = await res.json();

                const list = document.getElementById('api-keys-list');

                if (!data.api_keys || data.api_keys.length === 0) {
                    list.innerHTML = '<p style="color: #888; text-align: center;">Aucune API Key configurée</p>';
                    return;
                }

                let html = '<table style="margin-top: 10px;"><thead><tr><th>Nom</th><th>Clé</th><th>Statut</th><th>Créée le</th><th>Actions</th></tr></thead><tbody>';

                data.api_keys.forEach(key => {
                    const statusColor = key.enabled ? '#00aa00' : '#888';
                    const statusText = key.enabled ? '✅ Activée' : '❌ Désactivée';
                    const createdAt = new Date(key.created_at).toLocaleString('fr-FR');

                    html += `
                        <tr>
                            <td><strong>${key.name}</strong></td>
                            <td>
                                <code style="background: #0f0f0f; padding: 4px 8px; border-radius: 4px; font-size: 11px;">${key.key_masked || key.key}</code>
                                <button class="copy-btn" onclick="copyApiKey('${key.key}')" style="margin-left: 10px;">📋 Copier</button>
                            </td>
                            <td style="color: ${statusColor};">${statusText}</td>
                            <td style="color: #888; font-size: 12px;">${createdAt}</td>
                            <td>
                                <button class="button" style="font-size: 12px; padding: 5px 10px;" onclick="toggleApiKey('${key.key}', ${!key.enabled})">
                                    ${key.enabled ? '⏸️ Désactiver' : '▶️ Activer'}
                                </button>
                                <button class="button danger" style="font-size: 12px; padding: 5px 10px;" onclick="deleteApiKey('${key.key}')">🗑️</button>
                            </td>
                        </tr>
                    `;
                });

                html += '</tbody></table>';
                list.innerHTML = html;
            } catch (error) {
                console.error("Erreur chargement API keys:", error);
                document.getElementById('api-keys-list').innerHTML = '<p style="color: #ff4444;">Erreur lors du chargement des API keys</p>';
            }
        }

        async function createApiKey() {
            const name = document.getElementById('api-key-name').value.trim();

            if (!name) {
                alert("Veuillez donner un nom à l'API Key");
                return;
            }

            try {
                const res = await fetch('/api/auth/api-keys', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ name: name, enabled: true })
                });

                const data = await res.json();

                if (data.key) {
                    alert(`✅ API Key créée avec succès !\\n\\nClé: ${data.key}\\n\\nCopiez-la maintenant, elle ne sera plus affichée en entier.`);
                    document.getElementById('api-key-name').value = '';
                    await loadApiKeys();
                } else {
                    alert("❌ Erreur lors de la création de l'API Key");
                }
            } catch (error) {
                alert("❌ Erreur lors de la création de l'API Key");
                console.error(error);
            }
        }

        function copyApiKey(key) {
            navigator.clipboard.writeText(key).then(() => {
                alert('✅ API Key copiée dans le presse-papiers!');
            }).catch(() => {
                alert('❌ Erreur lors de la copie');
            });
        }

        async function deleteApiKey(key) {
            if (!confirm('Êtes-vous sûr de vouloir supprimer cette API Key ?')) {
                return;
            }

            try {
                const res = await fetch(`/api/auth/api-keys/${encodeURIComponent(key)}`, {
                    method: 'DELETE'
                });

                const data = await res.json();

                if (data.success) {
                    alert('✅ API Key supprimée');
                    await loadApiKeys();
                } else {
                    alert('❌ Erreur lors de la suppression');
                }
            } catch (error) {
                alert('❌ Erreur lors de la suppression');
                console.error(error);
            }
        }

        async function toggleApiKey(key, enabled) {
            try {
                const res = await fetch(`/api/auth/api-keys/${encodeURIComponent(key)}?enabled=${enabled}`, {
                    method: 'PATCH'
                });

                const data = await res.json();

                if (data.success) {
                    alert(`✅ API Key ${enabled ? 'activée' : 'désactivée'}`);
                    await loadApiKeys();
                } else {
                    alert('❌ Erreur lors de la modification');
                }
            } catch (error) {
                alert('❌ Erreur lors de la modification');
                console.error(error);
            }
        }

        document.addEventListener('DOMContentLoaded', async () => {
            console.log("🚀 Initialisation Grab2RSS v2.6.8...");

            try {
                await checkAuthStatus();
                await loadTrackers();
                await refreshData();
                await loadGrabs();

                setInterval(refreshData, 30000);

                console.log("✅ Application initialisée");
            } catch (error) {
                console.error("❌ Erreur initialisation:", error);
                alert("Erreur lors du chargement de l'application. Vérifiez la console (F12).");
            }
        });
    </script>
</body>
</html>"""
    return HTMLResponse(content=html_content)
