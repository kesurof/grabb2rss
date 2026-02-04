# scheduler.py
import threading
import logging
from datetime import datetime
from typing import Any
from apscheduler.schedulers.background import BackgroundScheduler

from prowlarr import fetch_history, extract_grabs
from torrent import download_torrent
from db import insert_grab, purge_by_retention, log_sync, init_db, is_duplicate, cleanup_orphan_torrents
from auth import cleanup_expired_sessions

logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler()
last_sync_time = None
last_sync_error = None
is_syncing = False
sync_lock = threading.Lock()

def sync_prowlarr():
    """Synchronise avec Prowlarr avec vérification Radarr/Sonarr"""
    global last_sync_time, last_sync_error, is_syncing

    with sync_lock:
        if is_syncing:
            logger.warning("Sync déjà en cours")
            return

        is_syncing = True

    try:
        # Lire la config depuis config.py (qui charge settings.yml)
        from config import (
            DEDUP_HOURS, AUTO_PURGE, RETENTION_HOURS,
            RADARR_URL, RADARR_API_KEY, RADARR_ENABLED,
            SONARR_URL, SONARR_API_KEY, SONARR_ENABLED
        )

        dedup_hours = DEDUP_HOURS
        auto_purge = AUTO_PURGE
        retention_hours = RETENTION_HOURS

        # Récupérer les URLs Radarr/Sonarr
        radarr_url = RADARR_URL if RADARR_ENABLED else None
        radarr_api_key = RADARR_API_KEY if RADARR_ENABLED else None
        sonarr_url = SONARR_URL if SONARR_ENABLED else None
        sonarr_api_key = SONARR_API_KEY if SONARR_ENABLED else None

        logger.info("Sync Prowlarr en cours... (%s)", datetime.utcnow().isoformat())

        # Récupérer les downloadId grabbed (choisis) depuis Radarr/Sonarr (si configurés ET activés)
        imported_download_ids = set()
        if (radarr_url and radarr_api_key) or (sonarr_url and sonarr_api_key):
            from radarr_sonarr import get_all_imported_download_ids
            imported_download_ids = get_all_imported_download_ids(
                radarr_url=radarr_url if radarr_url else None,
                radarr_api_key=radarr_api_key if radarr_api_key else None,
                sonarr_url=sonarr_url if sonarr_url else None,
                sonarr_api_key=sonarr_api_key if sonarr_api_key else None
            )
            logger.info("Vérification activée: %s downloadId grabbed", len(imported_download_ids))
        else:
            logger.info("Vérification Radarr/Sonarr désactivée (pas de config)")
        
        records = fetch_history()
        if not records:
            logger.warning("Aucun enregistrement Prowlarr")
            log_sync("success", None, 0, 0)
            last_sync_time = datetime.utcnow()
            last_sync_error = None
            return
        
        grabs_count = 0
        deduplicated_count = 0
        rejected_count = 0
        
        for grab in extract_grabs(records):
            try:
                # Vérifier la déduplication avec config dynamique
                if is_duplicate(grab["title"], dedup_hours):
                    deduplicated_count += 1
                    logger.info("Doublon (%sh): %s", dedup_hours, grab["title"])
                    continue
                
                # Télécharger le torrent
                torrent_file = download_torrent(grab["title"], grab["torrent_url"])
                
                # Vérifier si grabbed par Radarr/Sonarr (si activé)
                if imported_download_ids:
                    from radarr_sonarr import is_download_id_imported
                    if not is_download_id_imported(torrent_file, imported_download_ids):
                        rejected_count += 1
                        logger.info("Non grabbed par Radarr/Sonarr: %s", grab["title"])
                        continue
                
                # Insérer dans la BD
                success, message = insert_grab(grab, torrent_file)
                
                if success:
                    grabs_count += 1
                    logger.info("Grab ajouté: %s", grab["title"])
                else:
                    logger.info("%s: %s", message, grab["title"])
                    deduplicated_count += 1
                    
            except Exception as e:
                logger.error("Erreur grab %s: %s", grab["title"], e)
                continue
        
        # Purge automatique avec config dynamique
        if auto_purge and retention_hours:
            purged = purge_by_retention(retention_hours)
            if purged > 0:
                logger.info("Purge: %s anciens grabs supprimés", purged)

        # Nettoyage automatique des torrents orphelins
        orphans_count, orphans_files = cleanup_orphan_torrents()
        if orphans_count > 0:
            logger.info("Nettoyage: %s torrents orphelins supprimés", orphans_count)

        log_sync("success", None, grabs_count, deduplicated_count)
        last_sync_time = datetime.utcnow()
        last_sync_error = None
        
        if rejected_count > 0:
            logger.info(
                "Sync terminée: %s grabs, %s doublons, %s rejetés (non grabbed)",
                grabs_count,
                deduplicated_count,
                rejected_count
            )
        else:
            logger.info("Sync terminée: %s grabs, %s doublons", grabs_count, deduplicated_count)
        
    except Exception as e:
        error_msg = str(e)
        logger.error("Erreur sync: %s", error_msg)
        log_sync("error", error_msg, 0, 0)
        last_sync_error = error_msg
        logger.error("Erreur sync: %s", error_msg)
    
    finally:
        is_syncing = False

def start_scheduler():
    """Démarre le scheduler avec config depuis config.py"""
    init_db()

    # Vérifier si le setup est complété
    from config import is_setup_completed, SYNC_INTERVAL
    if not is_setup_completed():
        logger.info("Setup Wizard non complété - Scheduler en attente")
        logger.info("Configurez l'application via http://localhost:8000/setup")
        # On démarre quand même le scheduler mais sans job
        scheduler.add_job(
            cleanup_expired_sessions,
            "interval",
            seconds=3600,
            id="cleanup_sessions",
            name="Cleanup sessions expirées",
            replace_existing=True
        )
        scheduler.start()
        return

    # Lire l'intervalle depuis config.py
    sync_interval = SYNC_INTERVAL

    scheduler.add_job(
        sync_prowlarr,
        "interval",
        seconds=sync_interval,
        id="sync_prowlarr",
        name="Sync Prowlarr",
        replace_existing=True
    )

    scheduler.add_job(
        cleanup_expired_sessions,
        "interval",
        seconds=3600,
        id="cleanup_sessions",
        name="Cleanup sessions expirées",
        replace_existing=True
    )

    scheduler.start()
    logger.info("Scheduler démarré (intervalle: %ss)", sync_interval)

    # Sync immédiate au démarrage
    sync_prowlarr()

def stop_scheduler():
    """Arrête le scheduler"""
    scheduler.shutdown()
    logger.info("Scheduler arrêté")

def get_sync_status():
    """Retourne le statut de sync"""
    next_run = None
    if scheduler.get_job("sync_prowlarr"):
        next_run = scheduler.get_job("sync_prowlarr").next_run_time
    
    return {
        "last_sync": last_sync_time.isoformat() if last_sync_time else None,
        "last_error": last_sync_error,
        "is_running": is_syncing,
        "next_sync": next_run.isoformat() if next_run else None
    }

def trigger_sync():
    """Déclenche une sync immédiate (thread-safe)"""
    if not is_syncing:
        threading.Thread(target=sync_prowlarr, daemon=True).start()
        return True
    return False


def restart_scheduler_after_setup():
    """
    Redémarre le scheduler après completion du setup wizard.
    Utilisé après la première configuration.
    """
    try:
        # Arrêter les jobs existants
        if scheduler.get_job("sync_prowlarr"):
            scheduler.remove_job("sync_prowlarr")
        if scheduler.get_job("cleanup_sessions"):
            scheduler.remove_job("cleanup_sessions")

        # Relire la config depuis config.py
        from config import SYNC_INTERVAL
        sync_interval = SYNC_INTERVAL

        # Ajouter le nouveau job
        scheduler.add_job(
            sync_prowlarr,
            "interval",
            seconds=sync_interval,
            id="sync_prowlarr",
            name="Sync Prowlarr",
            replace_existing=True
        )

        scheduler.add_job(
            cleanup_expired_sessions,
            "interval",
            seconds=3600,
            id="cleanup_sessions",
            name="Cleanup sessions expirées",
            replace_existing=True
        )

        logger.info("Scheduler redémarré après setup (intervalle: %ss)", sync_interval)

        # Lancer une sync immédiate
        threading.Thread(target=sync_prowlarr, daemon=True).start()

        return True
    except Exception as e:
        logger.error("Erreur redémarrage scheduler: %s", e)
        return False
