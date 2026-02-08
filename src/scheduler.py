# scheduler.py
import threading
import logging
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler

from db import purge_by_retention, log_sync, init_db, cleanup_orphan_torrents
from auth import cleanup_expired_sessions
from config import is_setup_completed
from history_reconcile import sync_grab_history
import setup

logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler()
last_sync_time = None
last_sync_error = None
is_syncing = False
sync_lock = threading.Lock()

def _run_history_sync(full_scan: bool = False):
    """Synchronise l'historique consolide (pipeline fusionne)."""
    global last_sync_time, last_sync_error, is_syncing

    with sync_lock:
        if is_syncing:
            logger.warning("Sync déjà en cours")
            return
        is_syncing = True

    try:
        history_apps = setup.get_history_apps()
        if not history_apps:
            logger.info("Sync history ignorée: aucune app configurée")
            log_sync("success", None, 0, 0)
            last_sync_time = datetime.utcnow()
            last_sync_error = None
            return

        from config import (
            HISTORY_LOOKBACK_DAYS,
            HISTORY_DOWNLOAD_FROM_HISTORY,
            HISTORY_MIN_SCORE,
            HISTORY_STRICT_HASH,
            HISTORY_INGESTION_MODE,
        )
        if HISTORY_INGESTION_MODE == "webhook_only":
            logger.info("Sync history ignorée: ingestion_mode=webhook_only")
            log_sync("success", None, 0, 0)
            last_sync_time = datetime.utcnow()
            last_sync_error = None
            return
        logger.info("Sync historique consolide en cours... (%s)", datetime.utcnow().isoformat())
        result = sync_grab_history(
            history_apps=history_apps,
            lookback_days=HISTORY_LOOKBACK_DAYS,
            full_scan=full_scan,
            download_from_history=HISTORY_DOWNLOAD_FROM_HISTORY,
            min_score=HISTORY_MIN_SCORE,
            strict_hash=HISTORY_STRICT_HASH,
            ingestion_mode=HISTORY_INGESTION_MODE,
        )
        ingested = int(result.get("ingested", 0))
        inserted = int(result.get("inserted", 0))
        log_sync("success", None, ingested, inserted)
        last_sync_time = datetime.utcnow()
        last_sync_error = None
        logger.info("Sync historique consolide terminee: ingested=%s inserted=%s full_scan=%s", ingested, inserted, full_scan)
    except Exception as e:
        error_msg = str(e)
        logger.error("Erreur sync: %s", error_msg)
        log_sync("error", error_msg, 0, 0)
        last_sync_error = error_msg
    finally:
        is_syncing = False


def sync_grab_history_job():
    """Job scheduler de reconciliation historique consolide (incremental)."""
    _run_history_sync(full_scan=False)


def housekeeping_job():
    """Housekeeping périodique: sessions, purge et orphelins."""
    try:
        cleanup_expired_sessions()
    except Exception as exc:
        logger.warning("Housekeeping sessions: %s", exc)
    try:
        from config import AUTO_PURGE, RETENTION_HOURS
        if AUTO_PURGE and RETENTION_HOURS:
            purged = purge_by_retention(RETENTION_HOURS)
            if purged > 0:
                logger.info("Housekeeping: %s grabs purgés", purged)
    except Exception as exc:
        logger.warning("Housekeeping purge: %s", exc)
    try:
        orphans_count, _ = cleanup_orphan_torrents()
        if orphans_count > 0:
            logger.info("Housekeeping: %s torrents orphelins supprimés", orphans_count)
    except Exception as exc:
        logger.warning("Housekeeping torrents: %s", exc)

def start_scheduler():
    """Démarre le scheduler avec config depuis config.py"""
    init_db()

    # Vérifier si le setup est complété
    if not is_setup_completed():
        logger.info("Setup Wizard non complété - Scheduler en attente")
        logger.info("Configurez l'application via http://localhost:8000/setup")
        # On démarre quand même le scheduler, housekeeping uniquement
        scheduler.add_job(
            housekeeping_job,
            "interval",
            seconds=3600,
            id="housekeeping",
            name="Housekeeping",
            replace_existing=True
        )
        scheduler.start()
        return

    # Historique consolide (configurable, incremental) - pipeline officiel
    from config import HISTORY_SYNC_INTERVAL_SECONDS, HISTORY_INGESTION_MODE
    history_apps = setup.get_history_apps()
    if history_apps and HISTORY_INGESTION_MODE != "webhook_only":
        scheduler.add_job(
            sync_grab_history_job,
            "interval",
            seconds=HISTORY_SYNC_INTERVAL_SECONDS,
            id="sync_grab_history",
            name="Sync Historique Consolide",
            replace_existing=True
        )
    else:
        logger.info("Sync historique consolide non planifiee: apps absentes ou ingestion_mode=webhook_only")

    scheduler.add_job(
        housekeeping_job,
        "interval",
        seconds=3600,
        id="housekeeping",
        name="Housekeeping",
        replace_existing=True
    )

    scheduler.start()
    logger.info("Scheduler démarré (history_interval=%ss)", HISTORY_SYNC_INTERVAL_SECONDS)
    if history_apps and HISTORY_INGESTION_MODE != "webhook_only":
        threading.Thread(target=_run_history_sync, kwargs={"full_scan": False}, daemon=True).start()

def stop_scheduler():
    """Arrête le scheduler"""
    scheduler.shutdown()
    logger.info("Scheduler arrêté")

def get_sync_status():
    """Retourne le statut de sync"""
    next_run = None
    job = scheduler.get_job("sync_grab_history")
    if job:
        next_run = job.next_run_time
    
    return {
        "last_sync": last_sync_time.isoformat() if last_sync_time else None,
        "last_error": last_sync_error,
        "is_running": is_syncing,
        "next_sync": next_run.isoformat() if next_run else None
    }

def trigger_sync():
    """Déclenche une sync immédiate (thread-safe)"""
    if not is_syncing:
        threading.Thread(target=_run_history_sync, kwargs={"full_scan": False}, daemon=True).start()
        return True
    return False


def restart_scheduler_after_setup():
    """
    Redémarre le scheduler après completion du setup wizard.
    Utilisé après la première configuration.
    """
    try:
        # Arrêter les jobs existants
        if scheduler.get_job("sync_grab_history"):
            scheduler.remove_job("sync_grab_history")
        if scheduler.get_job("housekeeping"):
            scheduler.remove_job("housekeeping")

    # Historique consolide (configurable, incremental) - pipeline officiel
        from config import HISTORY_SYNC_INTERVAL_SECONDS, HISTORY_INGESTION_MODE
        history_apps = setup.get_history_apps()
        if history_apps and HISTORY_INGESTION_MODE != "webhook_only":
            scheduler.add_job(
                sync_grab_history_job,
                "interval",
                seconds=HISTORY_SYNC_INTERVAL_SECONDS,
                id="sync_grab_history",
                name="Sync Historique Consolide",
                replace_existing=True
            )
        else:
            logger.info("Sync historique consolide non planifiee: apps absentes ou ingestion_mode=webhook_only")

        scheduler.add_job(
            housekeeping_job,
            "interval",
            seconds=3600,
            id="housekeeping",
            name="Housekeeping",
            replace_existing=True
        )

        logger.info("Scheduler redémarré après setup (history_interval=%ss)", HISTORY_SYNC_INTERVAL_SECONDS)
        if history_apps and HISTORY_INGESTION_MODE != "webhook_only":
            threading.Thread(target=_run_history_sync, kwargs={"full_scan": False}, daemon=True).start()

        return True
    except Exception as e:
        logger.error("Erreur redémarrage scheduler: %s", e)
        return False
