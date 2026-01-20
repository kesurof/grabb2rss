# setup_routes.py
"""
Routes pour le setup wizard (première installation)
"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import Optional
import setup

router = APIRouter()


class SetupConfigModel(BaseModel):
    """Modèle pour la configuration initiale"""
    prowlarr_url: str
    prowlarr_api_key: str
    prowlarr_history_page_size: Optional[int] = 500

    radarr_url: Optional[str] = ""
    radarr_api_key: Optional[str] = ""
    radarr_enabled: Optional[bool] = False

    sonarr_url: Optional[str] = ""
    sonarr_api_key: Optional[str] = ""
    sonarr_enabled: Optional[bool] = False

    sync_interval: Optional[int] = 3600
    retention_hours: Optional[int] = 168
    auto_purge: Optional[bool] = True
    dedup_hours: Optional[int] = 168

    rss_domain: Optional[str] = "localhost:8000"
    rss_scheme: Optional[str] = "http"
    rss_title: Optional[str] = "Grab2RSS"
    rss_description: Optional[str] = "Prowlarr to RSS Feed"


@router.get("/setup", response_class=HTMLResponse)
async def setup_page():
    """Page de setup wizard"""
    if not setup.is_first_run():
        # Si déjà configuré, rediriger vers l'accueil
        return """
        <!DOCTYPE html>
        <html>
        <head>
            <meta http-equiv="refresh" content="0; url=/" />
        </head>
        <body>
            <p>Configuration déjà effectuée. Redirection...</p>
        </body>
        </html>
        """

    return """<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Grab2RSS - Configuration Initiale</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            background: linear-gradient(135deg, #0f0f0f 0%, #1a1a2e 100%);
            color: #e0e0e0;
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }
        .container {
            max-width: 800px;
            width: 100%;
            background: #1a1a1a;
            border-radius: 12px;
            box-shadow: 0 8px 32px rgba(0,0,0,0.4);
            padding: 40px;
        }
        header {
            text-align: center;
            margin-bottom: 40px;
            padding-bottom: 20px;
            border-bottom: 2px solid #1e90ff;
        }
        h1 {
            font-size: 32px;
            color: #1e90ff;
            margin-bottom: 10px;
        }
        .subtitle {
            color: #888;
            font-size: 14px;
        }
        .section {
            margin-bottom: 30px;
        }
        .section-title {
            color: #1e90ff;
            font-size: 18px;
            font-weight: 600;
            margin-bottom: 15px;
            display: flex;
            align-items: center;
        }
        .section-title::before {
            content: '';
            width: 4px;
            height: 20px;
            background: #1e90ff;
            margin-right: 10px;
            border-radius: 2px;
        }
        .form-group {
            margin-bottom: 20px;
        }
        label {
            display: block;
            margin-bottom: 8px;
            color: #e0e0e0;
            font-weight: 500;
            font-size: 14px;
        }
        label .required {
            color: #ff4444;
            margin-left: 4px;
        }
        label .optional {
            color: #888;
            font-size: 12px;
            font-weight: 400;
        }
        input[type="text"],
        input[type="number"],
        input[type="url"] {
            width: 100%;
            padding: 12px;
            background: #0f0f0f;
            border: 1px solid #333;
            border-radius: 6px;
            color: #e0e0e0;
            font-size: 14px;
            transition: border-color 0.3s;
        }
        input:focus {
            outline: none;
            border-color: #1e90ff;
            box-shadow: 0 0 0 3px rgba(30, 144, 255, 0.1);
        }
        .help-text {
            font-size: 12px;
            color: #888;
            margin-top: 5px;
        }
        .checkbox-group {
            display: flex;
            align-items: center;
            margin-top: 10px;
        }
        input[type="checkbox"] {
            width: 20px;
            height: 20px;
            margin-right: 10px;
            cursor: pointer;
        }
        .button-group {
            display: flex;
            gap: 15px;
            margin-top: 40px;
        }
        button {
            flex: 1;
            padding: 15px;
            border: none;
            border-radius: 6px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s;
        }
        .btn-primary {
            background: #1e90ff;
            color: white;
        }
        .btn-primary:hover {
            background: #0066cc;
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(30, 144, 255, 0.4);
        }
        .btn-secondary {
            background: #333;
            color: #e0e0e0;
        }
        .btn-secondary:hover {
            background: #444;
        }
        .alert {
            padding: 15px;
            border-radius: 6px;
            margin-bottom: 20px;
            display: none;
        }
        .alert.success {
            background: rgba(0, 200, 0, 0.1);
            border: 1px solid rgba(0, 200, 0, 0.3);
            color: #00ff00;
        }
        .alert.error {
            background: rgba(255, 68, 68, 0.1);
            border: 1px solid rgba(255, 68, 68, 0.3);
            color: #ff4444;
        }
        .loading {
            display: none;
            text-align: center;
            padding: 20px;
        }
        .spinner {
            border: 3px solid #333;
            border-top: 3px solid #1e90ff;
            border-radius: 50%;
            width: 40px;
            height: 40px;
            animation: spin 1s linear infinite;
            margin: 0 auto;
        }
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>🚀 Bienvenue sur Grab2RSS</h1>
            <p class="subtitle">Configuration initiale - Version 2.6.1</p>
        </header>

        <div id="alert" class="alert"></div>
        <div id="loading" class="loading">
            <div class="spinner"></div>
            <p style="margin-top: 15px; color: #888;">Validation et sauvegarde en cours...</p>
        </div>

        <form id="setupForm">
            <!-- Prowlarr (Obligatoire) -->
            <div class="section">
                <div class="section-title">🔍 Prowlarr (Obligatoire)</div>
                <div class="form-group">
                    <label>
                        URL de Prowlarr <span class="required">*</span>
                    </label>
                    <input type="url" id="prowlarr_url" name="prowlarr_url"
                           placeholder="http://prowlarr:9696" required>
                    <div class="help-text">
                        L'URL complète de votre instance Prowlarr (avec le port)
                    </div>
                </div>
                <div class="form-group">
                    <label>
                        Clé API Prowlarr <span class="required">*</span>
                    </label>
                    <input type="text" id="prowlarr_api_key" name="prowlarr_api_key"
                           placeholder="xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx" required>
                    <div class="help-text">
                        Vous la trouverez dans Prowlarr > Paramètres > Général > Sécurité
                    </div>
                </div>
                <div class="form-group">
                    <label>Taille de l'historique</label>
                    <input type="number" id="prowlarr_history_page_size"
                           name="prowlarr_history_page_size" value="500">
                    <div class="help-text">Nombre de grabs à récupérer par sync (défaut: 500)</div>
                </div>
            </div>

            <!-- Radarr (Optionnel) -->
            <div class="section">
                <div class="section-title">🎬 Radarr <span style="color: #888; font-size: 14px;">(Optionnel)</span></div>
                <div class="checkbox-group">
                    <input type="checkbox" id="radarr_enabled" name="radarr_enabled">
                    <label for="radarr_enabled" style="margin: 0;">
                        Activer le filtrage Radarr (afficher uniquement les grabs Radarr)
                    </label>
                </div>
                <div id="radarr_fields" style="margin-top: 15px; display: none;">
                    <div class="form-group">
                        <label>URL de Radarr</label>
                        <input type="url" id="radarr_url" name="radarr_url"
                               placeholder="http://radarr:7878">
                    </div>
                    <div class="form-group">
                        <label>Clé API Radarr</label>
                        <input type="text" id="radarr_api_key" name="radarr_api_key"
                               placeholder="xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx">
                    </div>
                </div>
            </div>

            <!-- Sonarr (Optionnel) -->
            <div class="section">
                <div class="section-title">📺 Sonarr <span style="color: #888; font-size: 14px;">(Optionnel)</span></div>
                <div class="checkbox-group">
                    <input type="checkbox" id="sonarr_enabled" name="sonarr_enabled">
                    <label for="sonarr_enabled" style="margin: 0;">
                        Activer le filtrage Sonarr (afficher uniquement les grabs Sonarr)
                    </label>
                </div>
                <div id="sonarr_fields" style="margin-top: 15px; display: none;">
                    <div class="form-group">
                        <label>URL de Sonarr</label>
                        <input type="url" id="sonarr_url" name="sonarr_url"
                               placeholder="http://sonarr:8989">
                    </div>
                    <div class="form-group">
                        <label>Clé API Sonarr</label>
                        <input type="text" id="sonarr_api_key" name="sonarr_api_key"
                               placeholder="xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx">
                    </div>
                </div>
            </div>

            <!-- Paramètres avancés -->
            <div class="section">
                <div class="section-title">⚙️ Paramètres</div>
                <div class="form-group">
                    <label>Intervalle de synchronisation (secondes)</label>
                    <input type="number" id="sync_interval" name="sync_interval" value="3600">
                    <div class="help-text">Fréquence de synchronisation avec Prowlarr (3600 = 1 heure)</div>
                </div>
                <div class="form-group">
                    <label>Rétention des torrents (heures)</label>
                    <input type="number" id="retention_hours" name="retention_hours" value="168">
                    <div class="help-text">Durée de conservation des torrents (168 = 7 jours)</div>
                </div>
                <div class="checkbox-group">
                    <input type="checkbox" id="auto_purge" name="auto_purge" checked>
                    <label for="auto_purge" style="margin: 0;">
                        Purge automatique des anciens torrents
                    </label>
                </div>
            </div>

            <!-- Boutons -->
            <div class="button-group">
                <button type="button" class="btn-secondary" onclick="testConnection()">
                    🔌 Tester la connexion
                </button>
                <button type="submit" class="btn-primary">
                    ✅ Enregistrer et démarrer
                </button>
            </div>
        </form>
    </div>

    <script>
        // Toggle Radarr fields
        document.getElementById('radarr_enabled').addEventListener('change', function() {
            document.getElementById('radarr_fields').style.display = this.checked ? 'block' : 'none';
        });

        // Toggle Sonarr fields
        document.getElementById('sonarr_enabled').addEventListener('change', function() {
            document.getElementById('sonarr_fields').style.display = this.checked ? 'block' : 'none';
        });

        // Test connection
        async function testConnection() {
            const url = document.getElementById('prowlarr_url').value;
            const apiKey = document.getElementById('prowlarr_api_key').value;

            if (!url || !apiKey) {
                showAlert('Veuillez remplir l\'URL et la clé API Prowlarr', 'error');
                return;
            }

            showAlert('Test de connexion en cours...', 'success');

            try {
                const response = await fetch('/api/setup/test-prowlarr', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ url, api_key: apiKey })
                });

                const data = await response.json();

                if (data.success) {
                    showAlert('✅ Connexion réussie à Prowlarr !', 'success');
                } else {
                    showAlert('❌ Erreur: ' + (data.error || 'Connexion échouée'), 'error');
                }
            } catch (error) {
                showAlert('❌ Erreur de connexion: ' + error.message, 'error');
            }
        }

        // Submit form
        document.getElementById('setupForm').addEventListener('submit', async function(e) {
            e.preventDefault();

            const formData = new FormData(e.target);
            const config = {
                prowlarr_url: formData.get('prowlarr_url'),
                prowlarr_api_key: formData.get('prowlarr_api_key'),
                prowlarr_history_page_size: parseInt(formData.get('prowlarr_history_page_size')),

                radarr_enabled: document.getElementById('radarr_enabled').checked,
                radarr_url: formData.get('radarr_url') || '',
                radarr_api_key: formData.get('radarr_api_key') || '',

                sonarr_enabled: document.getElementById('sonarr_enabled').checked,
                sonarr_url: formData.get('sonarr_url') || '',
                sonarr_api_key: formData.get('sonarr_api_key') || '',

                sync_interval: parseInt(formData.get('sync_interval')),
                retention_hours: parseInt(formData.get('retention_hours')),
                auto_purge: document.getElementById('auto_purge').checked,
                dedup_hours: 168
            };

            // Show loading
            document.getElementById('setupForm').style.display = 'none';
            document.getElementById('loading').style.display = 'block';

            try {
                const response = await fetch('/api/setup/save', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(config)
                });

                const data = await response.json();

                if (data.success) {
                    showAlert('✅ Configuration enregistrée ! Redirection...', 'success');
                    setTimeout(() => {
                        window.location.href = '/';
                    }, 2000);
                } else {
                    document.getElementById('setupForm').style.display = 'block';
                    document.getElementById('loading').style.display = 'none';
                    showAlert('❌ Erreur: ' + (data.error || 'Impossible de sauvegarder'), 'error');
                }
            } catch (error) {
                document.getElementById('setupForm').style.display = 'block';
                document.getElementById('loading').style.display = 'none';
                showAlert('❌ Erreur: ' + error.message, 'error');
            }
        });

        function showAlert(message, type) {
            const alert = document.getElementById('alert');
            alert.textContent = message;
            alert.className = 'alert ' + type;
            alert.style.display = 'block';

            if (type === 'success' && !message.includes('Test')) {
                setTimeout(() => {
                    alert.style.display = 'none';
                }, 3000);
            }
        }
    </script>
</body>
</html>"""


@router.post("/api/setup/test-prowlarr")
async def test_prowlarr(data: dict):
    """Teste la connexion à Prowlarr"""
    url = data.get("url")
    api_key = data.get("api_key")

    is_valid, error = setup.validate_prowlarr_config(url, api_key)

    if is_valid:
        return {"success": True}
    else:
        return {"success": False, "error": error}


@router.post("/api/setup/save")
async def save_setup(config: SetupConfigModel):
    """Sauvegarde la configuration initiale"""
    try:
        # Construire la config
        new_config = {
            "prowlarr": {
                "url": config.prowlarr_url,
                "api_key": config.prowlarr_api_key,
                "history_page_size": config.prowlarr_history_page_size
            },
            "radarr": {
                "url": config.radarr_url,
                "api_key": config.radarr_api_key,
                "enabled": config.radarr_enabled
            },
            "sonarr": {
                "url": config.sonarr_url,
                "api_key": config.sonarr_api_key,
                "enabled": config.sonarr_enabled
            },
            "sync": {
                "interval": config.sync_interval,
                "auto_purge": config.auto_purge,
                "retention_hours": config.retention_hours,
                "dedup_hours": config.dedup_hours
            },
            "rss": {
                "domain": config.rss_domain,
                "scheme": config.rss_scheme,
                "title": config.rss_title,
                "description": config.rss_description
            },
            "setup_completed": True
        }

        # Sauvegarder
        success = setup.save_config(new_config)

        if success:
            # Redémarrer le scheduler avec la nouvelle config
            from scheduler import restart_scheduler_after_setup
            scheduler_started = restart_scheduler_after_setup()

            return {
                "success": True,
                "message": "Configuration enregistrée",
                "scheduler_started": scheduler_started
            }
        else:
            raise HTTPException(status_code=500, detail="Erreur de sauvegarde")

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/setup/status")
async def setup_status():
    """Retourne le statut du setup"""
    return {
        "first_run": setup.is_first_run(),
        "config_exists": setup.CONFIG_FILE.exists()
    }
