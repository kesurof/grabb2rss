# setup_routes.py
"""
Routes pour le setup wizard (première installation)
"""
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from pathlib import Path
from typing import Optional
import setup

router = APIRouter()

# Utiliser un chemin absolu identique à api.py pour éviter les conflits
TEMPLATE_DIR = Path(__file__).parent.absolute() / "templates"
templates = Jinja2Templates(directory=str(TEMPLATE_DIR))


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
    rss_title: Optional[str] = "grabb2RSS"
    rss_description: Optional[str] = "Prowlarr to RSS Feed"

    # Configuration d'authentification
    auth_enabled: Optional[bool] = False
    auth_username: Optional[str] = ""
    auth_password: Optional[str] = ""


@router.get("/setup", response_class=HTMLResponse)
async def setup_page(request: Request):
    """Page de setup wizard"""
    # Injecter l'état du setup dans le template
    first_run = setup.is_first_run()
    config_exists = setup.CONFIG_FILE.exists()

    return templates.TemplateResponse("pages/setup.html", {
        "request": request,
        "first_run": first_run,
        "config_exists": config_exists
    })


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
        print("🔧 Début sauvegarde configuration setup...")
        print(f"   Prowlarr URL: {config.prowlarr_url}")

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

        # Ajouter la configuration d'authentification si activée
        if config.auth_enabled and config.auth_username and config.auth_password:
            from auth import hash_password
            print(f"🔐 Configuration de l'authentification pour {config.auth_username}")
            new_config["auth"] = {
                "enabled": True,
                "username": config.auth_username,
                "password_hash": hash_password(config.auth_password),
                "api_keys": []
            }
        else:
            print("ℹ️  Authentification désactivée")
            new_config["auth"] = {
                "enabled": False,
                "username": "",
                "password_hash": "",
                "api_keys": []
            }

        # Sauvegarder
        success = setup.save_config(new_config)

        if success:
            print("✅ Configuration sauvegardée avec succès")

            # CRITIQUE : Recharger la configuration dans le module config
            try:
                from config import reload_config
                reload_config()
                print("✅ Configuration rechargée dans l'application")
            except Exception as reload_err:
                print(f"⚠️  Erreur rechargement config: {reload_err}")

            # Redémarrer le scheduler avec la nouvelle config
            try:
                from scheduler import restart_scheduler_after_setup
                scheduler_started = restart_scheduler_after_setup()
                print(f"   Scheduler: {'démarré' if scheduler_started else 'erreur'}")
            except Exception as sched_err:
                print(f"⚠️  Erreur démarrage scheduler: {sched_err}")
                scheduler_started = False

            return {
                "success": True,
                "message": "Configuration enregistrée",
                "scheduler_started": scheduler_started
            }
        else:
            error_msg = "Impossible de sauvegarder la configuration. Vérifiez les permissions sur /config"
            print(f"❌ {error_msg}")
            raise HTTPException(status_code=500, detail=error_msg)

    except HTTPException:
        raise
    except Exception as e:
        error_msg = f"Erreur lors de la sauvegarde: {str(e)}"
        print(f"❌ {error_msg}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=error_msg)


@router.get("/api/setup/status")
async def setup_status():
    """Retourne le statut du setup"""
    return {
        "first_run": setup.is_first_run(),
        "config_exists": setup.CONFIG_FILE.exists()
    }
