# setup_routes.py
"""
Routes pour le setup wizard (première installation)
"""
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from typing import Optional
import setup
import logging
from version import APP_VERSION

logger = logging.getLogger(__name__)

router = APIRouter()

# Utiliser un chemin absolu identique à api.py pour éviter les conflits
from paths import TEMPLATES_DIR
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


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
    auth_cookie_secure: Optional[bool] = False


@router.get("/setup", response_class=HTMLResponse)
async def setup_page(request: Request):
    """Page de setup wizard"""
    from fastapi.responses import RedirectResponse
    from auth import is_auth_enabled, verify_session

    # Si setup déjà complété ET auth activée, vérifier l'authentification
    first_run = setup.is_first_run()
    if not first_run:
        # Setup complété, vérifier l'auth
        if is_auth_enabled():
            session_token = request.cookies.get('session_token')
            if not verify_session(session_token):
                # Non authentifié : rediriger vers login AVANT le rendu
                return RedirectResponse(url='/login', status_code=302)

    config_exists = setup.CONFIG_FILE.exists()

    return templates.TemplateResponse("pages/setup.html", {
        "request": request,
        "first_run": first_run,
        "config_exists": config_exists,
        "version": APP_VERSION
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
        logger.info("Début sauvegarde configuration setup...")
        logger.info("Prowlarr URL: %s", config.prowlarr_url)

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
            logger.info("Configuration de l'authentification pour %s", config.auth_username)
            new_config["auth"] = {
                "enabled": True,
                "username": config.auth_username,
                "password_hash": hash_password(config.auth_password),
                "api_keys": [],
                "cookie_secure": config.auth_cookie_secure
            }
        else:
            logger.info("Authentification désactivée")
            new_config["auth"] = {
                "enabled": False,
                "username": "",
                "password_hash": "",
                "api_keys": [],
                "cookie_secure": config.auth_cookie_secure
            }

        # Sauvegarder
        success = setup.save_config(new_config)

        if success:
            logger.info("Configuration sauvegardée avec succès")

            # CRITIQUE : Recharger la configuration dans le module config
            try:
                from config import reload_config
                reload_config()
                logger.info("Configuration rechargée dans l'application")
            except Exception as reload_err:
                logger.warning("Erreur rechargement config: %s", reload_err)

            # Redémarrer le scheduler avec la nouvelle config
            try:
                from scheduler import restart_scheduler_after_setup
                scheduler_started = restart_scheduler_after_setup()
                logger.info("Scheduler: %s", "démarré" if scheduler_started else "erreur")
            except Exception as sched_err:
                logger.warning("Erreur démarrage scheduler: %s", sched_err)
                scheduler_started = False

            return {
                "success": True,
                "message": "Configuration enregistrée",
                "scheduler_started": scheduler_started
            }
        else:
            error_msg = "Impossible de sauvegarder la configuration. Vérifiez les permissions sur le dossier de config"
            logger.error("%s", error_msg)
            raise HTTPException(status_code=500, detail=error_msg)

    except HTTPException:
        raise
    except Exception as e:
        error_msg = f"Erreur lors de la sauvegarde: {str(e)}"
        logger.error("%s", error_msg)
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
