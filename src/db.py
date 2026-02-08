# db.py
import sqlite3
import time
import threading
import hashlib
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple
from contextlib import contextmanager
from config import DB_PATH, TORRENT_DIR

logger = logging.getLogger(__name__)
_schema_lock = threading.Lock()
_schema_ready = False

@contextmanager
def get_db():
    """Context manager pour connexions DB - NOUVEAU"""
    conn = get_db_connection()
    try:
        yield conn
    finally:
        conn.close()

def _get_raw_connection() -> sqlite3.Connection:
    """Connexion SQLite sans migration automatique (usage interne)."""
    conn = sqlite3.connect(str(DB_PATH), timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.execute("PRAGMA busy_timeout=30000;")
    except sqlite3.OperationalError as e:
        logger.warning("Impossible d'activer WAL mode: %s", e)
        logger.info("Conseil: Vérifier les permissions sur le dossier data/")
    return conn


def get_db_connection():
    """Retourne une connexion SQLite avec optimisations"""
    conn = _get_raw_connection()
    _ensure_schema_once()
    return conn


def _ensure_schema_once() -> None:
    """Assure la migration DB une seule fois par process."""
    global _schema_ready
    if _schema_ready:
        return
    with _schema_lock:
        if _schema_ready:
            return
        try:
            migrate_db()
            logger.info("Schema DB prêt")
        except Exception as e:
            logger.error("Migration DB échouée: %s", e)
        _schema_ready = True

def init_config_from_env():
    """Initialise la config DB depuis settings.yml si vide"""
    try:
        from config import (
            PROWLARR_URL, PROWLARR_API_KEY,
            RETENTION_HOURS, AUTO_PURGE,
            RSS_DOMAIN, RSS_SCHEME, RADARR_URL, RADARR_API_KEY,
            SONARR_URL, SONARR_API_KEY, DESCRIPTIONS
        )

        # Vérifier si la config existe déjà
        existing = get_all_config()

        if not existing:
            logger.info("Initialisation de la configuration depuis settings.yml...")
            
            # Définir toutes les valeurs
            configs = {
                "PROWLARR_URL": (str(PROWLARR_URL), DESCRIPTIONS.get("PROWLARR_URL", "")),
                "PROWLARR_API_KEY": (str(PROWLARR_API_KEY), DESCRIPTIONS.get("PROWLARR_API_KEY", "")),
                "RADARR_URL": (str(RADARR_URL), "URL de Radarr (ex: http://localhost:7878) - Optionnel"),
                "RADARR_API_KEY": (str(RADARR_API_KEY), "Clé API Radarr - Optionnel"),
                "SONARR_URL": (str(SONARR_URL), "URL de Sonarr (ex: http://localhost:8989) - Optionnel"),
                "SONARR_API_KEY": (str(SONARR_API_KEY), "Clé API Sonarr - Optionnel"),
                "RETENTION_HOURS": (str(RETENTION_HOURS if RETENTION_HOURS else 0), DESCRIPTIONS.get("RETENTION_HOURS", "")),
                "AUTO_PURGE": (str(AUTO_PURGE).lower(), DESCRIPTIONS.get("AUTO_PURGE", "")),
                "RSS_DOMAIN": (str(RSS_DOMAIN), DESCRIPTIONS.get("RSS_DOMAIN", "")),
                "RSS_SCHEME": (str(RSS_SCHEME), DESCRIPTIONS.get("RSS_SCHEME", ""))
            }
            
            for key, (value, description) in configs.items():
                set_config(key, value, description)
            
            logger.info("%s paramètres initialisés", len(configs))
        else:
            logger.info("Configuration existante (%s paramètres)", len(existing))
            
    except Exception as e:
        logger.warning("Erreur initialisation config: %s", e)

def reload_config_from_env() -> int:
    """
    Force le rechargement de la configuration depuis settings.yml vers la DB
    ATTENTION : Écrase les valeurs existantes en DB avec celles de settings.yml
    Retourne le nombre de paramètres rechargés
    """
    try:
        from config import (
            PROWLARR_URL, PROWLARR_API_KEY,
            RETENTION_HOURS, AUTO_PURGE,
            RSS_DOMAIN, RSS_SCHEME, RADARR_URL, RADARR_API_KEY,
            SONARR_URL, SONARR_API_KEY, DESCRIPTIONS
        )

        logger.info("Rechargement de la configuration depuis settings.yml...")
        
        # Définir toutes les valeurs (écrase les existantes)
        configs = {
            "PROWLARR_URL": (str(PROWLARR_URL), DESCRIPTIONS.get("PROWLARR_URL", "")),
            "PROWLARR_API_KEY": (str(PROWLARR_API_KEY), DESCRIPTIONS.get("PROWLARR_API_KEY", "")),
            "RADARR_URL": (str(RADARR_URL), "URL de Radarr (ex: http://localhost:7878) - Optionnel"),
            "RADARR_API_KEY": (str(RADARR_API_KEY), "Clé API Radarr - Optionnel"),
            "SONARR_URL": (str(SONARR_URL), "URL de Sonarr (ex: http://localhost:8989) - Optionnel"),
            "SONARR_API_KEY": (str(SONARR_API_KEY), "Clé API Sonarr - Optionnel"),
            "RETENTION_HOURS": (str(RETENTION_HOURS if RETENTION_HOURS else 0), DESCRIPTIONS.get("RETENTION_HOURS", "")),
            "AUTO_PURGE": (str(AUTO_PURGE).lower(), DESCRIPTIONS.get("AUTO_PURGE", "")),
            "RSS_DOMAIN": (str(RSS_DOMAIN), DESCRIPTIONS.get("RSS_DOMAIN", "")),
            "RSS_SCHEME": (str(RSS_SCHEME), DESCRIPTIONS.get("RSS_SCHEME", ""))
        }
        
        # Écrase toutes les valeurs
        for key, (value, description) in configs.items():
            set_config(key, value, description)
        
        logger.info("%s paramètres rechargés depuis settings.yml", len(configs))
        return len(configs)
        
    except Exception as e:
        logger.warning("Erreur rechargement config: %s", e)
        raise

def init_db():
    """Initialise la base de données avec toutes les tables"""
    logger.info("Initialisation de la base de données: %s", DB_PATH)

    # Vérifier que le répertoire parent existe
    if not DB_PATH.parent.exists():
        logger.info("Création du répertoire: %s", DB_PATH.parent)
        try:
            DB_PATH.parent.mkdir(parents=True, exist_ok=True, mode=0o755)
        except Exception as e:
            logger.error("Erreur création répertoire: %s", e)
            raise

    conn = get_db_connection()
    try:
        # Table grabs
        conn.execute("""
        CREATE TABLE IF NOT EXISTS grabs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            prowlarr_id INTEGER UNIQUE,
            download_id TEXT,
            instance TEXT,
            grabbed_at TEXT NOT NULL,
            title TEXT NOT NULL,
            torrent_url TEXT NOT NULL,
            torrent_file TEXT NOT NULL,
            title_hash TEXT,
            tracker TEXT,
            indexer_id INTEGER,
            source_first_seen TEXT,
            source_last_seen TEXT,
            status TEXT,
            torrent_created_source TEXT,
            torrent_created_at TEXT,
            last_error TEXT,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """)

        # Table sync_log
        conn.execute("""
        CREATE TABLE IF NOT EXISTS sync_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sync_at TEXT DEFAULT CURRENT_TIMESTAMP,
            status TEXT,
            error TEXT,
            grabs_count INTEGER DEFAULT 0,
            deduplicated_count INTEGER DEFAULT 0
        )
        """)

        # Table config
        conn.execute("""
        CREATE TABLE IF NOT EXISTS config (
            key TEXT PRIMARY KEY,
            value TEXT,
            description TEXT,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """)

        # Table sessions (persistantes)
        conn.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            token TEXT PRIMARY KEY,
            created_at TEXT NOT NULL,
            expires_at TEXT NOT NULL
        )
        """)

        # Index pour performances
        conn.execute("CREATE INDEX IF NOT EXISTS idx_grabs_date ON grabs(grabbed_at DESC)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_grabs_title_hash ON grabs(title_hash)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_grabs_prowlarr ON grabs(prowlarr_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_grabs_tracker ON grabs(tracker)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_grabs_download_id ON grabs(download_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_grabs_instance ON grabs(instance)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_grabs_status ON grabs(status)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_grabs_instance_download ON grabs(instance, download_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_expires ON sessions(expires_at)")

        # Table grab_history (source secondaire Radarr/Sonarr)
        conn.execute("""
        CREATE TABLE IF NOT EXISTS grab_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            instance TEXT NOT NULL,
            raw_id INTEGER,
            event_type TEXT,
            download_id TEXT,
            source_title TEXT,
            indexer TEXT,
            size INTEGER,
            info_url TEXT,
            grabbed_at TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(instance, raw_id)
        )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_grab_history_instance ON grab_history(instance)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_grab_history_download_id ON grab_history(download_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_grab_history_date ON grab_history(grabbed_at DESC)")
        conn.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_grab_history_instance_download_unique
        ON grab_history(instance, download_id)
        WHERE download_id IS NOT NULL AND trim(download_id) != ''
        """)

        conn.commit()

        # Vérifier que la DB a bien été créée
        if DB_PATH.exists():
            size_mb = DB_PATH.stat().st_size / (1024 * 1024)
            logger.info("Base de données initialisée: %s (%.2f MB)", DB_PATH, size_mb)
        else:
            logger.warning("Fichier DB non trouvé après création: %s", DB_PATH)

        # Migration des colonnes si nécessaire
        migrate_db()
        init_config_from_env()

    except Exception as e:
        logger.error("Erreur initialisation DB: %s", e)
        import traceback
        traceback.print_exc()
        raise
    finally:
        conn.close()

def migrate_db():
    """Effectue les migrations nécessaires"""
    conn = _get_raw_connection()
    try:
        cursor = conn.execute("PRAGMA table_info(grabs)")
        columns = [row[1] for row in cursor.fetchall()]
        
        # Ajout colonne title_hash si manquante
        if "title_hash" not in columns:
            logger.info("Migration: Ajout colonne title_hash...")
            conn.execute("ALTER TABLE grabs ADD COLUMN title_hash TEXT")
            conn.commit()
        
        # Ajout colonne tracker si manquante
        if "tracker" not in columns:
            logger.info("Migration: Ajout colonne tracker...")
            conn.execute("ALTER TABLE grabs ADD COLUMN tracker TEXT")
            conn.commit()
        
        # Ajout colonne indexer_id si manquante
        if "indexer_id" not in columns:
            logger.info("Migration: Ajout colonne indexer_id...")
            conn.execute("ALTER TABLE grabs ADD COLUMN indexer_id INTEGER")
            conn.commit()

        # Ajout colonne download_id si manquante
        if "download_id" not in columns:
            logger.info("Migration: Ajout colonne download_id...")
            conn.execute("ALTER TABLE grabs ADD COLUMN download_id TEXT")
            conn.commit()

        # Colonnes modèle fusionné (grabs canonique)
        if "instance" not in columns:
            logger.info("Migration: Ajout colonne instance...")
            conn.execute("ALTER TABLE grabs ADD COLUMN instance TEXT")
            conn.commit()
        if "source_first_seen" not in columns:
            logger.info("Migration: Ajout colonne source_first_seen...")
            conn.execute("ALTER TABLE grabs ADD COLUMN source_first_seen TEXT")
            conn.commit()
        if "source_last_seen" not in columns:
            logger.info("Migration: Ajout colonne source_last_seen...")
            conn.execute("ALTER TABLE grabs ADD COLUMN source_last_seen TEXT")
            conn.commit()
        if "status" not in columns:
            logger.info("Migration: Ajout colonne status...")
            conn.execute("ALTER TABLE grabs ADD COLUMN status TEXT")
            conn.commit()
        if "torrent_created_source" not in columns:
            logger.info("Migration: Ajout colonne torrent_created_source...")
            conn.execute("ALTER TABLE grabs ADD COLUMN torrent_created_source TEXT")
            conn.commit()
        if "torrent_created_at" not in columns:
            logger.info("Migration: Ajout colonne torrent_created_at...")
            conn.execute("ALTER TABLE grabs ADD COLUMN torrent_created_at TEXT")
            conn.commit()
        if "last_error" not in columns:
            logger.info("Migration: Ajout colonne last_error...")
            conn.execute("ALTER TABLE grabs ADD COLUMN last_error TEXT")
            conn.commit()
        if "updated_at" not in columns:
            logger.info("Migration: Ajout colonne updated_at...")
            conn.execute("ALTER TABLE grabs ADD COLUMN updated_at TEXT")
            conn.commit()

        # Migration table legacy -> table cible
        table_exists_legacy = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='history_secondary'"
        ).fetchone()
        table_exists_target = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='grab_history'"
        ).fetchone()
        if table_exists_legacy and not table_exists_target:
            logger.info("Migration: renommage table history_secondary -> grab_history...")
            conn.execute("ALTER TABLE history_secondary RENAME TO grab_history")
            conn.commit()

        # Table grab_history si absente
        conn.execute("""
        CREATE TABLE IF NOT EXISTS grab_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            instance TEXT NOT NULL,
            raw_id INTEGER,
            event_type TEXT,
            download_id TEXT,
            source_title TEXT,
            indexer TEXT,
            size INTEGER,
            info_url TEXT,
            grabbed_at TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(instance, raw_id)
        )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_grab_history_instance ON grab_history(instance)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_grab_history_download_id ON grab_history(download_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_grab_history_date ON grab_history(grabbed_at DESC)")
        # Si les deux tables existent encore, fusionner puis supprimer la legacy.
        table_exists_legacy = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='history_secondary'"
        ).fetchone()
        if table_exists_legacy:
            logger.info("Migration: fusion history_secondary -> grab_history...")
            conn.execute("""
                INSERT OR IGNORE INTO grab_history
                (instance, raw_id, event_type, download_id, source_title, indexer, size, info_url, grabbed_at, created_at)
                SELECT instance, raw_id, event_type, download_id, source_title, indexer, size, info_url, grabbed_at, created_at
                FROM history_secondary
            """)
            conn.execute("DROP TABLE history_secondary")
            conn.commit()
        # Dédup canonique: conserver la dernière ligne par (instance, download_id)
        conn.execute("""
            DELETE FROM grab_history
            WHERE download_id IS NOT NULL AND trim(download_id) != ''
              AND id NOT IN (
                SELECT MAX(id)
                FROM grab_history
                WHERE download_id IS NOT NULL AND trim(download_id) != ''
                GROUP BY instance, download_id
              )
        """)
        conn.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_grab_history_instance_download_unique
        ON grab_history(instance, download_id)
        WHERE download_id IS NOT NULL AND trim(download_id) != ''
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_grabs_download_id ON grabs(download_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_grabs_instance ON grabs(instance)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_grabs_status ON grabs(status)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_grabs_instance_download ON grabs(instance, download_id)")

        # Backfill colonnes canonique (non destructif)
        conn.execute("UPDATE grabs SET instance = 'legacy' WHERE instance IS NULL OR trim(instance) = ''")
        conn.execute("UPDATE grabs SET source_first_seen = 'legacy' WHERE source_first_seen IS NULL OR trim(source_first_seen) = ''")
        conn.execute("UPDATE grabs SET source_last_seen = source_first_seen WHERE source_last_seen IS NULL OR trim(source_last_seen) = ''")
        conn.execute("""
            UPDATE grabs
            SET status = CASE
                WHEN torrent_file IS NOT NULL AND trim(torrent_file) != '' THEN 'downloaded'
                ELSE 'missing'
            END
            WHERE status IS NULL OR trim(status) = ''
        """)
        conn.execute("""
            UPDATE grabs
            SET updated_at = COALESCE(updated_at, created_at, grabbed_at, CURRENT_TIMESTAMP)
            WHERE updated_at IS NULL OR trim(updated_at) = ''
        """)
        conn.execute("""
            UPDATE grabs
            SET torrent_created_source = COALESCE(source_first_seen, 'legacy')
            WHERE (torrent_file IS NOT NULL AND trim(torrent_file) != '')
              AND (torrent_created_source IS NULL OR trim(torrent_created_source) = '')
        """)
        conn.execute("""
            UPDATE grabs
            SET torrent_created_at = COALESCE(updated_at, created_at, grabbed_at, CURRENT_TIMESTAMP)
            WHERE (torrent_file IS NOT NULL AND trim(torrent_file) != '')
              AND (torrent_created_at IS NULL OR trim(torrent_created_at) = '')
        """)
        conn.commit()

        # Créer table sessions si absente (pour compatibilité anciennes DB)
        conn.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            token TEXT PRIMARY KEY,
            created_at TEXT NOT NULL,
            expires_at TEXT NOT NULL
        )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_expires ON sessions(expires_at)")
        
        # Remplir les hashes existants
        rows = conn.execute("SELECT id, title FROM grabs WHERE title_hash IS NULL").fetchall()
        for row_id, title in rows:
            title_hash = calculate_title_hash(title)
            conn.execute("UPDATE grabs SET title_hash = ? WHERE id = ?", (title_hash, row_id))
        
        conn.commit()
        logger.info("Migration complète")

    except Exception as e:
        logger.warning("Migration: %s", e)
    finally:
        conn.close()

def calculate_title_hash(title: str) -> str:
    """Calcule le hash MD5 du titre (normalisé en lowercase)"""
    return hashlib.md5(title.lower().encode()).hexdigest()

def insert_grab(grab_data: dict, torrent_file: str) -> Tuple[bool, str]:
    """Insère un grab dans la base de données"""
    attempts = 5
    backoff = 0.15
    for attempt in range(1, attempts + 1):
        with get_db() as conn:
            try:
                title_hash = calculate_title_hash(grab_data["title"])
                instance = ((grab_data.get("instance") or "legacy").strip().lower()) or "legacy"
                source = (grab_data.get("source") or "legacy").strip() or "legacy"
                status = "downloaded" if torrent_file else "missing"
                now_iso = datetime.utcnow().isoformat() + "Z"

                # Idempotence par couple canonique (instance, download_id)
                canonical_download_id = grab_data.get("download_id")
                if canonical_download_id:
                    existing_canonical = conn.execute("""
                    SELECT id, source_first_seen, torrent_file FROM grabs
                    WHERE instance = ? AND download_id = ?
                    ORDER BY id DESC LIMIT 1
                    """, (instance, canonical_download_id)).fetchone()
                    if existing_canonical:
                        source_first_seen = existing_canonical["source_first_seen"] or source
                        conn.execute("""
                        UPDATE grabs
                        SET prowlarr_id = COALESCE(?, prowlarr_id),
                            grabbed_at = ?,
                            title = ?,
                            torrent_url = ?,
                            torrent_file = CASE
                                WHEN ? IS NOT NULL AND trim(?) != '' THEN ?
                                ELSE torrent_file
                            END,
                            title_hash = ?,
                            tracker = ?,
                            indexer_id = ?,
                            source_first_seen = ?,
                            source_last_seen = ?,
                            status = ?,
                            torrent_created_source = CASE
                                WHEN ? IS NOT NULL AND trim(?) != '' AND (torrent_file IS NULL OR trim(torrent_file) = '') THEN ?
                                ELSE torrent_created_source
                            END,
                            torrent_created_at = CASE
                                WHEN ? IS NOT NULL AND trim(?) != '' AND (torrent_file IS NULL OR trim(torrent_file) = '') THEN ?
                                ELSE torrent_created_at
                            END,
                            last_error = NULL,
                            updated_at = ?
                        WHERE id = ?
                        """, (
                            grab_data.get("prowlarr_id"),
                            grab_data["date"],
                            grab_data["title"],
                            grab_data["torrent_url"],
                            torrent_file, torrent_file, torrent_file,
                            title_hash,
                            grab_data.get("tracker"),
                            grab_data.get("indexer_id"),
                            source_first_seen,
                            source,
                            status,
                            torrent_file, torrent_file, source,
                            torrent_file, torrent_file, now_iso,
                            now_iso,
                            existing_canonical["id"]
                        ))
                        conn.commit()
                        return True, "Grab mis à jour (idempotent)"

                # Vérifier les doublons par prowlarr_id
                existing = conn.execute("""
                SELECT COUNT(*) FROM grabs WHERE prowlarr_id = ?
                """, (grab_data["prowlarr_id"],)).fetchone()

                if existing[0] > 0:
                    return False, "Prowlarr ID existe déjà"
                conn.execute("""
                INSERT INTO grabs 
                (prowlarr_id, download_id, instance, grabbed_at, title, torrent_url, torrent_file, title_hash, tracker, indexer_id,
                 source_first_seen, source_last_seen, status, torrent_created_source, torrent_created_at, last_error, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    grab_data["prowlarr_id"],
                    grab_data.get("download_id"),
                    instance,
                    grab_data["date"],
                    grab_data["title"],
                    grab_data["torrent_url"],
                    torrent_file,
                    title_hash,
                    grab_data.get("tracker"),
                    grab_data.get("indexer_id"),
                    source,
                    source,
                    status,
                    source if torrent_file else None,
                    now_iso if torrent_file else None,
                    None,
                    now_iso
                ))
                conn.commit()
                return True, "Grab inséré avec succès"
            except sqlite3.OperationalError as e:
                msg = str(e).lower()
                if "no column named download_id" in msg:
                    try:
                        logger.warning("Migration manquante détectée (download_id), tentative de migration...")
                        migrate_db()
                    except Exception:
                        pass
                    if attempt < attempts:
                        continue
                if "database is locked" in msg or "database is busy" in msg:
                    if attempt < attempts:
                        logger.warning("DB verrouillée, retry %s/%s", attempt, attempts)
                        time.sleep(backoff * attempt)
                        continue
                return False, str(e)
            except Exception as e:
                return False, str(e)
    return False, "DB verrouillée (retries épuisés)"


def upsert_grab_history(records: List[dict]) -> Dict[str, int]:
    """Insère des entrées d'historique consolidé (Radarr/Sonarr) avec déduplication."""
    if not records:
        return {"inserted": 0}
    inserted = 0
    updated = 0
    with get_db() as conn:
        try:
            for item in records:
                instance = ((item.get("instance") or "legacy").strip().lower()) or "legacy"
                raw_id = item.get("raw_id")
                event_type = item.get("event_type")
                download_id = item.get("download_id")
                source_title = item.get("source_title")
                indexer = item.get("indexer")
                size = item.get("size")
                info_url = item.get("info_url")
                grabbed_at = item.get("grabbed_at")

                # Clé canonique: instance + download_id
                if download_id and str(download_id).strip():
                    existing = conn.execute("""
                        SELECT id
                        FROM grab_history
                        WHERE instance = ? AND download_id = ?
                        LIMIT 1
                    """, (instance, download_id)).fetchone()
                    if existing:
                        conn.execute("""
                            UPDATE grab_history
                            SET raw_id = COALESCE(?, raw_id),
                                event_type = COALESCE(?, event_type),
                                source_title = COALESCE(?, source_title),
                                indexer = COALESCE(?, indexer),
                                size = COALESCE(?, size),
                                info_url = COALESCE(?, info_url),
                                grabbed_at = CASE
                                    WHEN ? IS NOT NULL AND trim(?) != ''
                                         AND (grabbed_at IS NULL OR ? > grabbed_at) THEN ?
                                    ELSE grabbed_at
                                END
                            WHERE id = ?
                        """, (
                            raw_id,
                            event_type,
                            source_title,
                            indexer,
                            size,
                            info_url,
                            grabbed_at, grabbed_at, grabbed_at, grabbed_at,
                            existing["id"],
                        ))
                        changed = conn.execute("SELECT changes()").fetchone()[0]
                        if changed:
                            updated += 1
                        continue

                conn.execute("""
                    INSERT OR IGNORE INTO grab_history
                    (instance, raw_id, event_type, download_id, source_title, indexer, size, info_url, grabbed_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    instance,
                    raw_id,
                    event_type,
                    download_id,
                    source_title,
                    indexer,
                    size,
                    info_url,
                    grabbed_at,
                ))
                changed = conn.execute("SELECT changes()").fetchone()[0]
                if changed:
                    inserted += 1
            conn.commit()
        except Exception as e:
            logger.error("Erreur insert grab_history: %s", e)
            raise
    return {"inserted": inserted, "updated": updated}


def get_history_inconsistencies(limit: int = 20) -> Dict[str, Any]:
    """Compare le store webhook (grabs) avec l'historique secondaire."""
    with get_db() as conn:
        # Missing in main (webhook)
        missing_main_rows = conn.execute("""
        SELECT hs.instance, COUNT(DISTINCT hs.download_id) as count
        FROM grab_history hs
        LEFT JOIN grabs g ON g.download_id = hs.download_id
        WHERE hs.download_id IS NOT NULL
          AND g.download_id IS NULL
          AND (hs.event_type = 'grabbed' OR hs.event_type IS NULL)
        GROUP BY hs.instance
        """).fetchall()

        # Missing in secondary
        missing_secondary = conn.execute("""
        SELECT COUNT(DISTINCT g.download_id) as count
        FROM grabs g
        LEFT JOIN grab_history hs ON hs.download_id = g.download_id
        WHERE g.download_id IS NOT NULL
          AND hs.download_id IS NULL
        """).fetchone()

        # Mismatch title (same download_id)
        mismatch_rows = conn.execute("""
        SELECT hs.instance, hs.download_id, g.title as webhook_title, hs.source_title as history_title
        FROM grab_history hs
        JOIN grabs g ON g.download_id = hs.download_id
        WHERE hs.source_title IS NOT NULL
          AND g.title IS NOT NULL
          AND lower(hs.source_title) != lower(g.title)
        LIMIT ?
        """, (limit,)).fetchall()

        samples_missing_main = conn.execute("""
        SELECT DISTINCT hs.instance, hs.download_id, hs.source_title
        FROM grab_history hs
        LEFT JOIN grabs g ON g.download_id = hs.download_id
        WHERE hs.download_id IS NOT NULL
          AND g.download_id IS NULL
          AND (hs.event_type = 'grabbed' OR hs.event_type IS NULL)
        LIMIT ?
        """, (limit,)).fetchall()

        samples_missing_secondary = conn.execute("""
        SELECT DISTINCT g.download_id, g.title
        FROM grabs g
        LEFT JOIN grab_history hs ON hs.download_id = g.download_id
        WHERE g.download_id IS NOT NULL
          AND hs.download_id IS NULL
        LIMIT ?
        """, (limit,)).fetchall()

    return {
        "missing_in_main": [dict(row) for row in missing_main_rows],
        "missing_in_secondary": int(missing_secondary[0] if missing_secondary else 0),
        "mismatched_titles": [dict(row) for row in mismatch_rows],
        "samples_missing_main": [dict(row) for row in samples_missing_main],
        "samples_missing_secondary": [dict(row) for row in samples_missing_secondary],
    }


def get_grab_history_list(
    limit: int = 200,
    instance: Optional[str] = None,
    tracker: Optional[str] = None,
    download_id: Optional[str] = None,
    status: Optional[str] = None,
    source: Optional[str] = None,
    dedup: bool = True
) -> List[dict]:
    """Liste l'historique consolidé avec provenance canonique (source)."""
    with get_db() as conn:
        params: List[Any] = []
        if dedup:
            query = """
            SELECT
                hs.id,
                hs.instance,
                hs.download_id,
                hs.source_title,
                hs.indexer,
                hs.size,
                hs.grabbed_at,
                gs.torrent_file,
                COALESCE(gs.status, 'missing') AS status,
                COALESCE(gs.source_first_seen, 'history_sync') AS source,
                COALESCE(gs.source_last_seen, 'history_sync') AS source_last_seen,
                CASE WHEN gs.has_grab IS NULL THEN 0 ELSE 1 END AS in_webhook
            FROM grab_history hs
            JOIN (
                SELECT instance, download_id, MAX(grabbed_at) AS max_grabbed_at
                FROM grab_history
                WHERE download_id IS NOT NULL
                GROUP BY instance, download_id
            ) latest
              ON latest.instance = hs.instance
             AND latest.download_id = hs.download_id
             AND latest.max_grabbed_at = hs.grabbed_at
            LEFT JOIN (
                SELECT
                    LOWER(instance) AS instance_norm,
                    download_id,
                    1 AS has_grab,
                    MAX(CASE WHEN torrent_file IS NOT NULL AND torrent_file != '' THEN torrent_file END) AS torrent_file,
                    MAX(status) AS status,
                    MIN(source_first_seen) AS source_first_seen,
                    MAX(source_last_seen) AS source_last_seen
                FROM grabs
                WHERE download_id IS NOT NULL
                GROUP BY LOWER(instance), download_id
            ) gs ON gs.instance_norm = LOWER(hs.instance) AND gs.download_id = hs.download_id
            WHERE 1=1
            """
        else:
            query = """
            SELECT
                hs.id,
                hs.instance,
                hs.download_id,
                hs.source_title,
                hs.indexer,
                hs.size,
                hs.grabbed_at,
                gs.torrent_file,
                COALESCE(gs.status, 'missing') AS status,
                COALESCE(gs.source_first_seen, 'history_sync') AS source,
                COALESCE(gs.source_last_seen, 'history_sync') AS source_last_seen,
                CASE WHEN gs.has_grab IS NULL THEN 0 ELSE 1 END AS in_webhook
            FROM grab_history hs
            LEFT JOIN (
                SELECT
                    LOWER(instance) AS instance_norm,
                    download_id,
                    1 AS has_grab,
                    MAX(CASE WHEN torrent_file IS NOT NULL AND torrent_file != '' THEN torrent_file END) AS torrent_file,
                    MAX(status) AS status,
                    MIN(source_first_seen) AS source_first_seen,
                    MAX(source_last_seen) AS source_last_seen
                FROM grabs
                WHERE download_id IS NOT NULL
                GROUP BY LOWER(instance), download_id
            ) gs ON gs.instance_norm = LOWER(hs.instance) AND gs.download_id = hs.download_id
            WHERE 1=1
            """
        if instance:
            query += " AND hs.instance = ?"
            params.append(instance)
        if tracker:
            query += " AND hs.indexer = ?"
            params.append(tracker)
        if download_id:
            query += " AND hs.download_id = ?"
            params.append(download_id)
        if status:
            query += " AND COALESCE(gs.status, 'missing') = ?"
            params.append(status)
        if source:
            query += " AND COALESCE(gs.source_first_seen, 'history_sync') = ?"
            params.append(source)
        query += " ORDER BY hs.grabbed_at DESC LIMIT ?"
        params.append(limit)
        rows = conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]

def get_grab_history_record(download_id: str, instance: Optional[str] = None) -> Optional[dict]:
    """Récupère une entrée grab_history par download_id (et instance optionnelle)."""
    if not download_id:
        return None
    with get_db() as conn:
        params: List[Any] = [download_id]
        query = """
        SELECT
            hs.id,
            hs.instance,
            hs.download_id,
            hs.source_title,
            hs.indexer,
            hs.size,
            hs.info_url,
            hs.grabbed_at
        FROM grab_history hs
        WHERE hs.download_id = ?
        """
        if instance:
            query += " AND hs.instance = ?"
            params.append(instance)
        query += " ORDER BY hs.grabbed_at DESC LIMIT 1"
        row = conn.execute(query, params).fetchone()
        return dict(row) if row else None

def get_grabs(limit: int = 50, tracker_filter: Optional[str] = None) -> List[dict]:
    """Récupère les derniers grabs avec déduplication optionnelle et filtre tracker"""
    with get_db() as conn:
        query = """
        SELECT
            id, prowlarr_id, download_id, instance, grabbed_at, title,
            torrent_file, tracker, source_first_seen, source_last_seen, status
        FROM grabs
        WHERE 1=1
        """
        params = []
        
        # Filtre par tracker
        if tracker_filter and tracker_filter != "all":
            query += " AND tracker = ?"
            params.append(tracker_filter)
        
        query += " ORDER BY grabbed_at DESC LIMIT ?"
        params.append(limit)
        
        rows = conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]

def get_trackers() -> List[str]:
    """Récupère la liste des trackers uniques"""
    with get_db() as conn:
        rows = conn.execute("""
        SELECT DISTINCT tracker FROM grabs 
        WHERE tracker IS NOT NULL 
        ORDER BY tracker
        """).fetchall()
        return [row[0] for row in rows if row[0]]

def get_stats() -> dict:
    """Récupère les statistiques complètes"""
    with get_db() as conn:
        total = conn.execute("SELECT COUNT(*) FROM grabs").fetchone()[0]
        latest = conn.execute(
            "SELECT grabbed_at FROM grabs ORDER BY grabbed_at DESC LIMIT 1"
        ).fetchone()
        oldest = conn.execute(
            "SELECT grabbed_at FROM grabs ORDER BY grabbed_at ASC LIMIT 1"
        ).fetchone()
        
        # Stats par tracker
        tracker_stats = conn.execute("""
        SELECT tracker, COUNT(*) as count FROM grabs 
        WHERE tracker IS NOT NULL
        GROUP BY tracker
        ORDER BY count DESC
        """).fetchall()
        
        # Top 10 des torrents
        top_torrents = conn.execute("""
        SELECT title, grabbed_at FROM grabs
        ORDER BY grabbed_at DESC LIMIT 10
        """).fetchall()
        
        # Grabs par jour (derniers 30 jours)
        grabs_by_day = conn.execute("""
        SELECT DATE(grabbed_at) as day, COUNT(*) as count
        FROM grabs
        WHERE grabbed_at >= datetime('now', '-30 days')
        GROUP BY day
        ORDER BY day DESC
        LIMIT 30
        """).fetchall()
        
        # Taille du stockage
        size = sum(f.stat().st_size for f in TORRENT_DIR.rglob("*.torrent")) / (1024 * 1024) if TORRENT_DIR.exists() else 0
        
        return {
            "total_grabs": total,
            "latest_grab": latest[0] if latest else None,
            "oldest_grab": oldest[0] if oldest else None,
            "storage_size_mb": round(size, 2),
            "tracker_stats": [{"tracker": t[0], "count": t[1]} for t in tracker_stats],
            "top_torrents": [{"title": t[0], "date": t[1]} for t in top_torrents],
            "grabs_by_day": [{"day": d[0], "count": d[1]} for d in grabs_by_day]
        }

def purge_by_retention(hours: int) -> int:
    """Supprime les grabs plus anciens que X heures"""
    if hours is None:
        return 0
    
    with get_db() as conn:
        cutoff = (datetime.utcnow() - timedelta(hours=hours)).isoformat() + "Z"
        cursor = conn.execute("DELETE FROM grabs WHERE grabbed_at < ?", (cutoff,))
        conn.commit()
        return cursor.rowcount

def purge_all() -> int:
    """Supprime tous les grabs"""
    with get_db() as conn:
        cursor = conn.execute("DELETE FROM grabs")
        conn.commit()
        return cursor.rowcount

def log_sync(status: str, error: Optional[str] = None, grabs_count: int = 0, deduplicated_count: int = 0):
    """Enregistre un sync dans le log"""
    with get_db() as conn:
        conn.execute("""
        INSERT INTO sync_log (status, error, grabs_count, deduplicated_count)
        VALUES (?, ?, ?, ?)
        """, (status, error, grabs_count, deduplicated_count))
        conn.commit()

def get_sync_logs(limit: int = 20) -> List[dict]:
    """Récupère les derniers logs de sync"""
    with get_db() as conn:
        rows = conn.execute("""
        SELECT sync_at, status, error, grabs_count, deduplicated_count
        FROM sync_log
        ORDER BY sync_at DESC
        LIMIT ?
        """, (limit,)).fetchall()
        return [dict(row) for row in rows]

def get_config(key: str) -> Optional[str]:
    """Récupère une valeur de config"""
    with get_db() as conn:
        result = conn.execute(
            "SELECT value FROM config WHERE key = ?", (key,)
        ).fetchone()
        return result[0] if result else None

def set_config(key: str, value: str, description: str = ""):
    """Définit une valeur de config"""
    with get_db() as conn:
        conn.execute("""
        INSERT OR REPLACE INTO config (key, value, description, updated_at)
        VALUES (?, ?, ?, CURRENT_TIMESTAMP)
        """, (key, value, description))
        conn.commit()

def get_all_config() -> Dict[str, Any]:
    """Récupère toute la config"""
    with get_db() as conn:
        rows = conn.execute("SELECT key, value, description FROM config").fetchall()
        return {row[0]: {"value": row[1], "description": row[2]} for row in rows}

def vacuum_database() -> Tuple[float, float]:
    """
    Optimise la base de données SQLite (VACUUM)
    Retourne (taille_avant_MB, taille_après_MB)
    """
    # Taille avant
    size_before = DB_PATH.stat().st_size / (1024 * 1024) if DB_PATH.exists() else 0
    
    with get_db() as conn:
        # VACUUM nettoie et compacte la base
        conn.execute("VACUUM")
        conn.commit()
    
    # Taille après
    size_after = DB_PATH.stat().st_size / (1024 * 1024) if DB_PATH.exists() else 0
    
    return size_before, size_after

def get_db_stats() -> dict:
    """Récupère des statistiques sur la base de données"""
    with get_db() as conn:
        grabs_count = conn.execute("SELECT COUNT(*) FROM grabs").fetchone()[0]
        sync_logs_count = conn.execute("SELECT COUNT(*) FROM sync_log").fetchone()[0]
        config_count = conn.execute("SELECT COUNT(*) FROM config").fetchone()[0]

        size_mb = DB_PATH.stat().st_size / (1024 * 1024) if DB_PATH.exists() else 0

        return {
            "path": str(DB_PATH),
            "size_mb": round(size_mb, 2),
            "grabs": grabs_count,
            "sync_logs": sync_logs_count,
            "config_entries": config_count
        }

def get_torrent_files_with_info() -> List[dict]:
    """
    Récupère la liste des fichiers torrents avec leurs informations associées depuis la base de données
    """
    torrent_files_info = []

    if not TORRENT_DIR.exists():
        return torrent_files_info

    with get_db() as conn:
        # Récupérer tous les fichiers torrents du système de fichiers
        torrent_files_on_disk = {f.name: f for f in TORRENT_DIR.glob("*.torrent")}

        # Pour chaque fichier, récupérer ses infos depuis la DB
        for filename, filepath in torrent_files_on_disk.items():
            # Chercher les infos du grab associé
            grab_info = conn.execute("""
                SELECT id, grabbed_at, title, tracker, torrent_file
                FROM grabs
                WHERE torrent_file = ?
            """, (filename,)).fetchone()

            file_stats = filepath.stat()

            torrent_info = {
                "filename": filename,
                "size_bytes": file_stats.st_size,
                "size_mb": round(file_stats.st_size / (1024 * 1024), 2),
                "modified_at": datetime.fromtimestamp(file_stats.st_mtime).isoformat() + "Z",
                "has_grab": grab_info is not None
            }

            # Ajouter les infos du grab si disponibles
            if grab_info:
                torrent_info.update({
                    "grab_id": grab_info[0],
                    "grabbed_at": grab_info[1],
                    "title": grab_info[2],
                    "tracker": grab_info[3] or "N/A"
                })
            else:
                # Torrent orphelin (sans grab associé)
                torrent_info.update({
                    "grab_id": None,
                    "grabbed_at": None,
                    "title": filename.replace(".torrent", ""),
                    "tracker": "N/A"
                })

            torrent_files_info.append(torrent_info)

    # Trier par date de grab (les plus récents en premier)
    torrent_files_info.sort(key=lambda x: x.get("grabbed_at") or x.get("modified_at"), reverse=True)

    return torrent_files_info

def cleanup_orphan_torrents() -> Tuple[int, List[str]]:
    """
    Supprime les fichiers torrents qui n'ont pas de grab associé dans la base de données
    Retourne (nombre_supprimés, liste_fichiers_supprimés)
    """
    deleted_count = 0
    deleted_files = []

    if not TORRENT_DIR.exists():
        return deleted_count, deleted_files

    with get_db() as conn:
        # Récupérer tous les fichiers torrents du système de fichiers
        torrent_files_on_disk = list(TORRENT_DIR.glob("*.torrent"))

        for filepath in torrent_files_on_disk:
            filename = filepath.name

            # Vérifier si ce fichier est référencé dans la DB
            grab = conn.execute("""
                SELECT COUNT(*) FROM grabs WHERE torrent_file = ?
            """, (filename,)).fetchone()

            # Si le fichier n'est pas référencé, le supprimer
            if grab[0] == 0:
                try:
                    filepath.unlink()
                    deleted_count += 1
                    deleted_files.append(filename)
                except Exception as e:
                    logger.warning("Erreur lors de la suppression de %s: %s", filename, e)

    return deleted_count, deleted_files

def delete_torrent_file(filename: str) -> bool:
    """
    Supprime un fichier torrent spécifique (et éventuellement son grab associé)
    """
    if not TORRENT_DIR.exists():
        return False

    torrent_path = resolve_torrent_path(filename)
    if torrent_path is None:
        logger.warning("Nom de torrent invalide: %s", filename)
        return False

    if not torrent_path.exists():
        return False

    try:
        torrent_path.unlink()
        return True
    except Exception as e:
        logger.warning("Erreur lors de la suppression de %s: %s", filename, e)
        return False

def resolve_torrent_path(filename: str) -> Optional[Path]:
    """
    Valide le nom de fichier torrent et retourne un chemin sûr dans TORRENT_DIR.
    Refuse les séparateurs de chemin et force l'extension .torrent.
    """
    if not filename:
        return None
    if "/" in filename or "\\" in filename:
        return None
    if not filename.endswith(".torrent"):
        return None
    if Path(filename).name != filename:
        return None

    torrent_dir = TORRENT_DIR.resolve()
    candidate = (TORRENT_DIR / filename).resolve()

    try:
        candidate.relative_to(torrent_dir)
    except ValueError:
        return None

    return candidate

def purge_all_torrents() -> Tuple[int, float]:
    """
    Supprime TOUS les fichiers torrents du dossier
    Retourne (nombre_supprimés, taille_libérée_MB)
    """
    deleted_count = 0
    size_freed = 0

    if not TORRENT_DIR.exists():
        return deleted_count, size_freed

    torrent_files = list(TORRENT_DIR.glob("*.torrent"))

    for filepath in torrent_files:
        try:
            size_freed += filepath.stat().st_size
            filepath.unlink()
            deleted_count += 1
        except Exception as e:
            logger.warning("Erreur lors de la suppression de %s: %s", filepath.name, e)

    size_freed_mb = size_freed / (1024 * 1024)
    return deleted_count, round(size_freed_mb, 2)

def delete_log(log_id: int) -> bool:
    """Supprime un log de synchronisation spécifique"""
    with get_db() as conn:
        try:
            cursor = conn.execute("DELETE FROM sync_log WHERE id = ?", (log_id,))
            conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            logger.warning("Erreur lors de la suppression du log %s: %s", log_id, e)
            return False

def purge_all_logs() -> int:
    """Supprime tous les logs de synchronisation"""
    with get_db() as conn:
        cursor = conn.execute("DELETE FROM sync_log")
        conn.commit()
        return cursor.rowcount


def purge_all_db() -> Dict[str, int]:
    """Nettoie la DB (grabs, logs, sessions) sans toucher la config."""
    with get_db() as conn:
        grabs = conn.execute("DELETE FROM grabs").rowcount
        logs = conn.execute("DELETE FROM sync_log").rowcount
        sessions = conn.execute("DELETE FROM sessions").rowcount
        conn.commit()
        return {
            "grabs": grabs,
            "logs": logs,
            "sessions": sessions
        }
