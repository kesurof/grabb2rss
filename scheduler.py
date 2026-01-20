# scheduler.py
import threading
import logging
from datetime import datetime
from typing import Any
from apscheduler.schedulers.background import BackgroundScheduler

from prowlarr import fetch_history, extract_grabs
from torrent import download_torrent
from db import insert_grab, purge_by_retention, log_sync, init_db, is_duplicate, get_config

logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler()
last_sync_time = None
last_sync_error = None
is_syncing = False
sync_lock = threading.Lock()

def get_config_value(key: str, default: Any) -> Any:
    """Récupère une valeur de config depuis la DB ou .env"""
    try:
        from config import SYNC_INTERVAL, AUTO_PURGE, RETENTION_HOURS, DEDUP_HOURS
        
        defaults = {
            "SYNC_INTERVAL": SYNC_INTERVAL,
            "AUTO_PURGE": AUTO_PURGE,
            "RETENTION_HOURS": RETENTION_HOURS,
            "DEDUP_HOURS": DEDUP_HOURS
        }
        
        # Essayer de lire depuis la DB (priorité)
        db_value = get_config(key)
        if db_value is not None:
            # Convertir selon le type
            if key in ["SYNC_INTERVAL", "RETENTION_HOURS", "DEDUP_HOURS"]:
                return int(db_value)
            elif key == "AUTO_PURGE":
                return db_value.lower() == "true"
            return db_value
        
        # Fallback sur .env
        return defaults.get(key, default)
    except Exception as e:
        print(f"⚠️  Erreur lecture config {key}: {e}")
        return default

def sync_prowlarr():
    """Synchronise avec Prowlarr avec vérification Radarr/Sonarr"""
    global last_sync_time, last_sync_error, is_syncing
    
    with sync_lock:
        if is_syncing:
            print("⚠️  Sync déjà en cours...")
            return
        
        is_syncing = True
    
    try:
        # Lire la config dynamiquement
        dedup_hours = get_config_value("DEDUP_HOURS", 168)
        auto_purge = get_config_value("AUTO_PURGE", True)
        retention_hours = get_config_value("RETENTION_HOURS", 168)
        
        # Récupérer les URLs Radarr/Sonarr
        radarr_url = get_config_value("RADARR_URL", "")
        radarr_api_key = get_config_value("RADARR_API_KEY", "")
        sonarr_url = get_config_value("SONARR_URL", "")
        sonarr_api_key = get_config_value("SONARR_API_KEY", "")
        
        print(f"⏱️  Sync Prowlarr en cours... ({datetime.utcnow().isoformat()})")
        
        # Récupérer les downloadId grabbed (choisis) depuis Radarr/Sonarr (si configurés)
        imported_download_ids = set()
        if (radarr_url and radarr_api_key) or (sonarr_url and sonarr_api_key):
            from radarr_sonarr import get_all_imported_download_ids
            imported_download_ids = get_all_imported_download_ids(
                radarr_url=radarr_url if radarr_url else None,
                radarr_api_key=radarr_api_key if radarr_api_key else None,
                sonarr_url=sonarr_url if sonarr_url else None,
                sonarr_api_key=sonarr_api_key if sonarr_api_key else None
            )
            print(f"🔍 Vérification activée: {len(imported_download_ids)} downloadId grabbed")
        else:
            print("ℹ️  Vérification Radarr/Sonarr désactivée (pas de config)")
        
        records = fetch_history()
        if not records:
            print("⚠️  Aucun enregistrement Prowlarr")
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
                    print(f"⊘ Doublon ({dedup_hours}h): {grab['title']}")
                    continue
                
                # Télécharger le torrent
                torrent_file = download_torrent(grab["title"], grab["torrent_url"])
                
                # Vérifier si grabbed par Radarr/Sonarr (si activé)
                if imported_download_ids:
                    from radarr_sonarr import is_download_id_imported
                    if not is_download_id_imported(torrent_file, imported_download_ids):
                        rejected_count += 1
                        print(f"⊘ Non grabbed par Radarr/Sonarr: {grab['title']}")
                        continue
                
                # Insérer dans la BD
                success, message = insert_grab(grab, torrent_file)
                
                if success:
                    grabs_count += 1
                    print(f"✔️  {grab['title']}")
                else:
                    print(f"⊘ {message}: {grab['title']}")
                    deduplicated_count += 1
                    
            except Exception as e:
                print(f"❌ {grab['title']}: {e}")
                continue
        
        # Purge automatique avec config dynamique
        if auto_purge and retention_hours:
            purged = purge_by_retention(retention_hours)
            if purged > 0:
                print(f"🗑️  Purge: {purged} anciens grabs supprimés")
        
        log_sync("success", None, grabs_count, deduplicated_count)
        last_sync_time = datetime.utcnow()
        last_sync_error = None
        
        if rejected_count > 0:
            print(f"✅ Sync terminée: {grabs_count} grabs, {deduplicated_count} doublons, {rejected_count} rejetés (non grabbed)")
        else:
            print(f"✅ Sync terminée: {grabs_count} grabs, {deduplicated_count} doublons")
        
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Erreur sync: {error_msg}")
        log_sync("error", error_msg, 0, 0)
        last_sync_error = error_msg
        print(f"❌ Erreur sync: {error_msg}")
    
    finally:
        is_syncing = False

def start_scheduler():
    """Démarre le scheduler avec config dynamique"""
    init_db()

    # Vérifier si le setup est complété
    from config import is_setup_completed
    if not is_setup_completed():
        print("⚙️  Setup Wizard non complété - Scheduler en attente")
        print("💡 Configurez l'application via http://localhost:8000/setup")
        # On démarre quand même le scheduler mais sans job
        scheduler.start()
        return

    # Lire l'intervalle depuis la config dynamique
    sync_interval = get_config_value("SYNC_INTERVAL", 3600)

    scheduler.add_job(
        sync_prowlarr,
        "interval",
        seconds=sync_interval,
        id="sync_prowlarr",
        name="Sync Prowlarr",
        replace_existing=True
    )

    scheduler.start()
    print(f"🚀 Scheduler démarré (intervalle: {sync_interval}s)")

    # Sync immédiate au démarrage
    sync_prowlarr()

def stop_scheduler():
    """Arrête le scheduler"""
    scheduler.shutdown()
    print("🛑 Scheduler arrêté")

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

        # Relire la config
        sync_interval = get_config_value("SYNC_INTERVAL", 3600)

        # Ajouter le nouveau job
        scheduler.add_job(
            sync_prowlarr,
            "interval",
            seconds=sync_interval,
            id="sync_prowlarr",
            name="Sync Prowlarr",
            replace_existing=True
        )

        print(f"🔄 Scheduler redémarré après setup (intervalle: {sync_interval}s)")

        # Lancer une sync immédiate
        threading.Thread(target=sync_prowlarr, daemon=True).start()

        return True
    except Exception as e:
        print(f"❌ Erreur redémarrage scheduler: {e}")
        return False
