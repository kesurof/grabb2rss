# api.py
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import Response, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import logging

from config import TORRENT_DIR, DB_PATH, DEDUP_HOURS, DESCRIPTIONS, PROWLARR_URL, PROWLARR_API_KEY
from db import (
    init_db, get_grabs, get_stats, purge_all, purge_by_retention,
    get_config, set_config, get_all_config, get_sync_logs, get_trackers, get_db
)
from rss import generate_rss, generate_torrent_json
from models import GrabOut, GrabStats, SyncStatus
from scheduler import start_scheduler, stop_scheduler, get_sync_status, trigger_sync

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Grab2RSS API",
    description="API pour Grab2RSS - Convert Prowlarr grabs en RSS",
    version="2.3.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Monter le dossier torrents
if TORRENT_DIR.exists():
    app.mount("/torrents", StaticFiles(directory=str(TORRENT_DIR)), name="torrents")

# ==================== LIFECYCLE ====================

@app.on_event("startup")
async def startup():
    """Au démarrage de l'app"""
    init_db()
    start_scheduler()
    print("✅ Application démarrée v2.3")

@app.on_event("shutdown")
async def shutdown():
    """À l'arrêt de l'app"""
    stop_scheduler()
    print("✅ Application arrêtée")

# ==================== HEALTH ====================

@app.get("/health")
async def health():
    """Healthcheck complet avec vérification de tous les composants"""
    from datetime import datetime
    import requests
    
    checks = {
        "status": "ok",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "2.3.0",
        "components": {
            "database": "unknown",
            "prowlarr": "unknown",
            "scheduler": "unknown"
        }
    }
    
    # 1. Vérifier la base de données
    try:
        if DB_PATH.exists():
            # Tester une requête simple
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
    
    # Déterminer le code de statut HTTP
    status_code = 200 if checks["status"] == "ok" else 503
    
    return JSONResponse(checks, status_code=status_code)

@app.get("/debug")
async def debug_info():
    """Informations de debug"""
    from datetime import datetime
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
    """Récupère toute la configuration"""
    try:
        config = get_all_config()
        for key, desc in DESCRIPTIONS.items():
            if key not in config:
                config[key] = {"value": "", "description": desc}
        return config
    except Exception as e:
        logger.error(f"Erreur get_config: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/config")
async def update_configuration(config_data: dict):
    """Met à jour la configuration"""
    try:
        for key, data in config_data.items():
            if isinstance(data, dict):
                value = str(data.get("value", ""))
                desc = data.get("description", DESCRIPTIONS.get(key, ""))
            else:
                value = str(data)
                desc = DESCRIPTIONS.get(key, "")
            
            set_config(key, value, desc)
        
        return {
            "status": "updated",
            "message": "Configuration mise à jour"
        }
    except Exception as e:
        logger.error(f"Erreur update_config: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ==================== WEB UI ====================

@app.get("/test", response_class=HTMLResponse)
async def test_ui():
    """Interface de test simple"""
    from pathlib import Path
    test_file = Path(__file__).parent / "test_simple.html"
    if test_file.exists():
        return test_file.read_text()
    else:
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
<h2>Test API JavaScript</h2>
<button onclick="testAPI()" style="background: #1e90ff; color: white; border: none; padding: 10px 20px; border-radius: 4px; cursor: pointer;">🔍 Tester</button>
<pre id="result" style="background: #1a1a1a; padding: 15px; margin-top: 15px; border-radius: 4px;"></pre>
<script>
async function testAPI() {
    const result = document.getElementById('result');
    result.textContent = '⏳ Test en cours...';
    try {
        const response = await fetch('/api/stats');
        const data = await response.json();
        result.textContent = '✅ Succès !\\n\\n' + JSON.stringify(data, null, 2);
    } catch (error) {
        result.textContent = '❌ Erreur: ' + error.message;
    }
}
</script>
</body></html>"""

@app.get("/minimal", response_class=HTMLResponse)
async def minimal_ui():
    """Interface ultra-minimaliste sans JavaScript complexe"""
    return """<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Grab2RSS - Test Minimal</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            max-width: 800px;
            margin: 50px auto;
            padding: 20px;
            background: #0f0f0f;
            color: #fff;
        }
        h1 { color: #1e90ff; }
        a {
            color: #1e90ff;
            text-decoration: none;
            display: block;
            padding: 10px;
            margin: 10px 0;
            background: #1a1a1a;
            border-radius: 4px;
        }
        a:hover { background: #2a2a2a; }
        .success { color: #00ff00; }
    </style>
</head>
<body>
    <h1>🧪 Grab2RSS - Test Minimal</h1>
    
    <p class="success">✅ Si vous voyez cette page, le serveur fonctionne !</p>
    
    <h2>📋 Liens de Test</h2>
    
    <a href="/api/stats" target="_blank">📊 Stats (JSON)</a>
    <a href="/api/grabs" target="_blank">📋 Grabs (JSON)</a>
    <a href="/api/trackers" target="_blank">🏷️ Trackers (JSON)</a>
    <a href="/rss" target="_blank">📡 Flux RSS (XML)</a>
    <a href="/rss/torrent.json" target="_blank">📡 Flux RSS (JSON)</a>
    <a href="/health" target="_blank">💚 Health Check</a>
    <a href="/debug" target="_blank">🔍 Debug Info</a>
    <a href="/" target="_blank">🏠 Interface Complète</a>
    
    <h2>📝 Informations</h2>
    <ul>
        <li>Serveur : <strong>http://localhost:8000</strong></li>
        <li>Version : <strong>2.3.0</strong></li>
        <li>Status : <strong class="success">ONLINE</strong></li>
    </ul>
    
    <h2>🧪 Test JavaScript</h2>
    <p>Si JavaScript fonctionne, vous verrez "OK" ci-dessous :</p>
    <p id="js-test" style="color: #ff0000;">❌ JavaScript NON chargé</p>
    
    <script>
        // Test ultra-simple
        document.getElementById('js-test').innerHTML = '<span style="color: #00ff00;">✅ JavaScript OK</span>';
        console.log('✅ JavaScript fonctionne');
    </script>
    
    <h2>💡 Prochaines Étapes</h2>
    <ol>
        <li>Si vous voyez "✅ JavaScript OK" ci-dessus, tout fonctionne</li>
        <li>Sinon, ouvrez la console (F12) pour voir les erreurs</li>
        <li>Testez les liens ci-dessus pour vérifier l'API</li>
    </ol>
</body>
</html>"""

@app.get("/", response_class=HTMLResponse)
async def web_ui():
    """Interface Web complète (CORRIGÉE)"""
    return """<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Grab2RSS v2.3 - Dashboard</title>
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
        
        h2 { color: #1e90ff; margin: 30px 0 15px 0; }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>📡 Grab2RSS v2.3</h1>
            <p class="subtitle">Convertisseur Prowlarr → RSS avec Flux Personnalisés</p>
        </header>

        <div class="tabs">
            <button class="tab-button active" onclick="switchTab('dashboard')">📊 Dashboard</button>
            <button class="tab-button" onclick="switchTab('grabs')">📋 Grabs</button>
            <button class="tab-button" onclick="switchTab('stats')">📈 Statistiques</button>
            <button class="tab-button" onclick="switchTab('rss')">📡 Flux RSS</button>
            <button class="tab-button" onclick="switchTab('logs')">📝 Logs</button>
            <button class="tab-button" onclick="switchTab('config')">⚙️ Configuration</button>
        </div>

        <!-- TAB: DASHBOARD -->
        <div id="dashboard" class="tab-content active">
            <div class="grid">
                <div class="card">
                    <h3>Total Grabs</h3>
                    <div class="value" id="total-grabs">-</div>
                </div>
                <div class="card">
                    <h3>Stockage</h3>
                    <div class="value"><span id="storage-size">-</span><span class="unit">MB</span></div>
                </div>
                <div class="card">
                    <h3>Dernier Grab</h3>
                    <div class="value" id="latest-grab" style="font-size: 14px; margin-top: 10px;">-</div>
                </div>
                <div class="card">
                    <h3>Statut Sync</h3>
                    <div class="status" id="sync-status"></div>
                    <div class="date" id="next-sync" style="margin-top: 10px;">-</div>
                </div>
            </div>

            <h2>🎯 Actions</h2>
            <div class="actions">
                <button class="button" onclick="refreshData()">🔄 Actualiser</button>
                <button class="button success" id="sync-btn" onclick="syncNow()">📡 Sync Maintenant</button>
                <button class="button danger" onclick="purgeAllGrabs()">🗑️ Vider Tout</button>
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
            document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
            document.querySelectorAll('.tab-button').forEach(el => el.classList.remove('active'));
            document.getElementById(tab).classList.add('active');
            event.target.classList.add('active');
            
            if (tab === 'config') loadConfig();
            if (tab === 'logs') loadLogs();
            if (tab === 'grabs') loadGrabs();
            if (tab === 'stats') loadStats();
            if (tab === 'rss') loadRssUrls();
        }

        function loadRssUrls() {
            const baseUrl = getRssBaseUrl();
            document.getElementById('rss-global-xml').textContent = `${baseUrl}/rss`;
            document.getElementById('rss-global-json').textContent = `${baseUrl}/rss/torrent.json`;
            updateTrackerRssUrls();
        }

        function updateTrackerRssUrls() {
            const tracker = document.getElementById('tracker-filter-rss').value;
            const baseUrl = getRssBaseUrl();
            
            if (tracker === 'all') {
                document.getElementById('rss-tracker-xml').textContent = `${baseUrl}/rss`;
                document.getElementById('rss-tracker-json').textContent = `${baseUrl}/rss/torrent.json`;
            } else {
                document.getElementById('rss-tracker-xml').textContent = `${baseUrl}/rss/tracker/${encodeURIComponent(tracker)}`;
                document.getElementById('rss-tracker-json').textContent = `${baseUrl}/rss/tracker/${encodeURIComponent(tracker)}/json`;
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
                console.log("📊 Chargement des trackers...");
                
                const res = await fetch(`${API_BASE}/trackers`);
                if (!res.ok) throw new Error(`Trackers API error: ${res.status}`);
                
                const data = await res.json();
                allTrackers = data.trackers;
                
                console.log(`✅ ${allTrackers.length} trackers chargés`);
                
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
                // Continuer même si les trackers ne sont pas disponibles
            }
        }

        async function filterGrabs() {
            const tracker = document.getElementById('tracker-filter-grabs').value;
            const url = `${API_BASE}/grabs?limit=100&tracker=${encodeURIComponent(tracker)}`;
            
            try {
                const grabs = await fetch(url).then(r => r.json());
                const tbody = document.getElementById("grabs-table");
                tbody.innerHTML = grabs.length ? grabs.map(g => `
                    <tr>
                        <td class="date">${new Date(g.grabbed_at).toLocaleString('fr-FR')}</td>
                        <td>${g.title}</td>
                        <td><strong style="color: #1e90ff;">${g.tracker || 'N/A'}</strong></td>
                        <td><a href="/torrents/${encodeURIComponent(g.torrent_file)}" target="_blank" style="color: #1e90ff; text-decoration: none;">📥 Download</a></td>
                    </tr>
                `).join("") : `<tr><td colspan="4" style="text-align: center; color: #888;">Aucun grab</td></tr>`;
            } catch (e) {
                console.error("Erreur filterGrabs:", e);
            }
        }

        async function loadStats() {
            try {
                const res = await fetch(`${API_BASE}/stats`);
                statsData = await res.json();
                
                // Stats par tracker - Pie Chart
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
                
                // Grabs par jour - Line Chart
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
                
                // Top torrents - Bar Chart
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
                
                // Stats tableau
                const total = statsData.tracker_stats.reduce((a, b) => a + b.count, 0);
                let tbody = document.getElementById('tracker-stats-body');
                tbody.innerHTML = statsData.tracker_stats.map(t => `
                    <tr>
                        <td><strong>${t.tracker}</strong></td>
                        <td>${t.count}</td>
                        <td>${((t.count / total) * 100).toFixed(1)}%</td>
                    </tr>
                `).join("");
                
            } catch (e) {
                console.error("Erreur loadStats:", e);
            }
        }

        async function refreshData() {
            try {
                console.log("🔄 Rafraîchissement des données...");
                
                const [stats, sync] = await Promise.all([
                    fetch(`${API_BASE}/stats`).then(r => {
                        if (!r.ok) throw new Error(`Stats API error: ${r.status}`);
                        return r.json();
                    }),
                    fetch(`${API_BASE}/sync/status`).then(r => {
                        if (!r.ok) throw new Error(`Sync API error: ${r.status}`);
                        return r.json();
                    })
                ]);

                document.getElementById("total-grabs").textContent = stats.total_grabs;
                document.getElementById("storage-size").textContent = stats.storage_size_mb;
                document.getElementById("latest-grab").textContent = stats.latest_grab ? new Date(stats.latest_grab).toLocaleString('fr-FR') : "-";

                const statusEl = document.getElementById("sync-status");
                
                // Déterminer le vrai statut
                let statusClass = "status offline";
                let statusText = "Inactif";
                
                if (sync.is_running) {
                    // Sync en cours
                    statusClass = "status online";
                    statusText = "Sync en cours...";
                } else if (sync.next_sync) {
                    // Scheduler actif avec prochaine sync planifiée
                    statusClass = "status online";
                    statusText = "Actif";
                } else if (sync.last_sync) {
                    // A déjà sync mais pas de prochaine sync planifiée
                    statusClass = "status offline";
                    statusText = "Arrêté";
                } else {
                    // Jamais sync
                    statusClass = "status offline";
                    statusText = "En attente";
                }
                
                statusEl.className = statusClass;
                statusEl.textContent = statusText;

                document.getElementById("next-sync").textContent = sync.next_sync ? `Prochain: ${new Date(sync.next_sync).toLocaleString('fr-FR')}` : "-";
                
                console.log("✅ Données rafraîchies");
            } catch (e) {
                console.error("❌ Erreur refreshData:", e);
                // Ne pas bloquer l'interface sur une erreur
            }
        }

        async function loadGrabs() {
            await filterGrabs();
        }

        async function loadLogs() {
            try {
                const logs = await fetch(`${API_BASE}/sync/logs?limit=50`).then(r => r.json());
                const tbody = document.getElementById("logs-table");
                tbody.innerHTML = logs.length ? logs.map(l => `
                    <tr>
                        <td class="date">${new Date(l.sync_at).toLocaleString('fr-FR')}</td>
                        <td><span class="status ${l.status === 'success' ? 'online' : 'offline'}">${l.status}</span></td>
                        <td>${l.grabs_count}</td>
                        <td>${l.deduplicated_count || 0}</td>
                        <td style="color: #ff4444; font-size: 12px;">${l.error ? l.error.substring(0, 50) : '-'}</td>
                    </tr>
                `).join("") : `<tr><td colspan="5" style="text-align: center; color: #888;">Aucun log</td></tr>`;
            } catch (e) {
                console.error("Erreur loadLogs:", e);
            }
        }

        async function loadConfig() {
            try {
                const response = await fetch(`${API_BASE}/config`);
                configData = await response.json();
                
                const form = document.getElementById("config-form");
                form.innerHTML = Object.entries(configData).map(([key, data]) => `
                    <div class="form-group">
                        <label for="${key}">${key}</label>
                        <input type="text" id="${key}" name="${key}" value="${data.value || ''}" placeholder="${data.description}">
                        <small>${data.description}</small>
                    </div>
                `).join("");
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
                
                const res = await fetch(`${API_BASE}/config`, {
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
                await fetch(`${API_BASE}/sync/trigger`, { method: "POST" });
                
                setTimeout(() => {
                    refreshData();
                    btn.disabled = false;
                    btn.textContent = "📡 Sync Maintenant";
                }, 2000);
            } catch (e) {
                alert("Erreur: " + e);
                btn.disabled = false;
                btn.textContent = "📡 Sync Maintenant";
            }
        }

        async function purgeAllGrabs() {
            if (confirm("⚠️  Êtes-vous CERTAIN ? Cela supprimera TOUS les grabs !")) {
                try {
                    const res = await fetch(`${API_BASE}/purge/all`, { method: "POST" });
                    const data = await res.json();
                    alert("✅ " + data.message);
                    refreshData();
                    loadGrabs();
                } catch (e) {
                    alert("❌ Erreur: " + e);
                }
            }
        }

        // Initialisation
        document.addEventListener('DOMContentLoaded', async () => {
            console.log("🚀 Initialisation Grab2RSS...");
            
            try {
                await loadTrackers();
                await refreshData();
                await loadGrabs();
                
                // Rafraîchir toutes les 30s
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
