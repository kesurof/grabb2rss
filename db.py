# db.py
import sqlite3
import hashlib
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple
from contextlib import contextmanager
from config import DB_PATH, TORRENT_DIR

@contextmanager
def get_db():
    """Context manager pour connexions DB - NOUVEAU"""
    conn = get_db_connection()
    try:
        yield conn
    finally:
        conn.close()

def get_db_connection():
    """Retourne une connexion SQLite avec optimisations"""
    conn = sqlite3.connect(str(DB_PATH), timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    
    # Tenter d'activer le mode WAL (ignorer si erreur de permissions)
    try:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
    except sqlite3.OperationalError as e:
        print(f"⚠️  Impossible d'activer WAL mode: {e}")
        print("💡 Conseil: Vérifier les permissions sur le dossier data/")
    
    return conn

def init_config_from_env():
    """Initialise la config DB depuis les variables d'environnement si vide"""
    try:
        from config import (
            PROWLARR_URL, PROWLARR_API_KEY, PROWLARR_HISTORY_PAGE_SIZE,
            SYNC_INTERVAL, RETENTION_HOURS, AUTO_PURGE, DEDUP_HOURS,
            RSS_DOMAIN, RSS_SCHEME, RADARR_URL, RADARR_API_KEY,
            SONARR_URL, SONARR_API_KEY, DESCRIPTIONS
        )
        
        # Vérifier si la config existe déjà
        existing = get_all_config()
        
        if not existing:
            print("📝 Initialisation de la configuration depuis .env...")
            
            # Définir toutes les valeurs
            configs = {
                "PROWLARR_URL": (str(PROWLARR_URL), DESCRIPTIONS.get("PROWLARR_URL", "")),
                "PROWLARR_API_KEY": (str(PROWLARR_API_KEY), DESCRIPTIONS.get("PROWLARR_API_KEY", "")),
                "PROWLARR_HISTORY_PAGE_SIZE": (str(PROWLARR_HISTORY_PAGE_SIZE), DESCRIPTIONS.get("PROWLARR_HISTORY_PAGE_SIZE", "")),
                "RADARR_URL": (str(RADARR_URL), "URL de Radarr (ex: http://localhost:7878) - Optionnel"),
                "RADARR_API_KEY": (str(RADARR_API_KEY), "Clé API Radarr - Optionnel"),
                "SONARR_URL": (str(SONARR_URL), "URL de Sonarr (ex: http://localhost:8989) - Optionnel"),
                "SONARR_API_KEY": (str(SONARR_API_KEY), "Clé API Sonarr - Optionnel"),
                "SYNC_INTERVAL": (str(SYNC_INTERVAL), DESCRIPTIONS.get("SYNC_INTERVAL", "")),
                "RETENTION_HOURS": (str(RETENTION_HOURS if RETENTION_HOURS else 0), DESCRIPTIONS.get("RETENTION_HOURS", "")),
                "AUTO_PURGE": (str(AUTO_PURGE).lower(), DESCRIPTIONS.get("AUTO_PURGE", "")),
                "DEDUP_HOURS": (str(DEDUP_HOURS), DESCRIPTIONS.get("DEDUP_HOURS", "")),
                "RSS_DOMAIN": (str(RSS_DOMAIN), DESCRIPTIONS.get("RSS_DOMAIN", "")),
                "RSS_SCHEME": (str(RSS_SCHEME), DESCRIPTIONS.get("RSS_SCHEME", ""))
            }
            
            for key, (value, description) in configs.items():
                set_config(key, value, description)
            
            print(f"✅ {len(configs)} paramètres initialisés")
        else:
            print(f"ℹ️  Configuration existante ({len(existing)} paramètres)")
            
    except Exception as e:
        print(f"⚠️  Erreur initialisation config: {e}")

def reload_config_from_env() -> int:
    """
    Force le rechargement de la configuration depuis .env vers la DB
    ATTENTION : Écrase les valeurs existantes en DB avec celles de .env
    Retourne le nombre de paramètres rechargés
    """
    try:
        from config import (
            PROWLARR_URL, PROWLARR_API_KEY, PROWLARR_HISTORY_PAGE_SIZE,
            SYNC_INTERVAL, RETENTION_HOURS, AUTO_PURGE, DEDUP_HOURS,
            RSS_DOMAIN, RSS_SCHEME, RADARR_URL, RADARR_API_KEY,
            SONARR_URL, SONARR_API_KEY, DESCRIPTIONS
        )
        
        print("🔄 Rechargement de la configuration depuis .env...")
        
        # Définir toutes les valeurs (écrase les existantes)
        configs = {
            "PROWLARR_URL": (str(PROWLARR_URL), DESCRIPTIONS.get("PROWLARR_URL", "")),
            "PROWLARR_API_KEY": (str(PROWLARR_API_KEY), DESCRIPTIONS.get("PROWLARR_API_KEY", "")),
            "PROWLARR_HISTORY_PAGE_SIZE": (str(PROWLARR_HISTORY_PAGE_SIZE), DESCRIPTIONS.get("PROWLARR_HISTORY_PAGE_SIZE", "")),
            "RADARR_URL": (str(RADARR_URL), "URL de Radarr (ex: http://localhost:7878) - Optionnel"),
            "RADARR_API_KEY": (str(RADARR_API_KEY), "Clé API Radarr - Optionnel"),
            "SONARR_URL": (str(SONARR_URL), "URL de Sonarr (ex: http://localhost:8989) - Optionnel"),
            "SONARR_API_KEY": (str(SONARR_API_KEY), "Clé API Sonarr - Optionnel"),
            "SYNC_INTERVAL": (str(SYNC_INTERVAL), DESCRIPTIONS.get("SYNC_INTERVAL", "")),
            "RETENTION_HOURS": (str(RETENTION_HOURS if RETENTION_HOURS else 0), DESCRIPTIONS.get("RETENTION_HOURS", "")),
            "AUTO_PURGE": (str(AUTO_PURGE).lower(), DESCRIPTIONS.get("AUTO_PURGE", "")),
            "DEDUP_HOURS": (str(DEDUP_HOURS), DESCRIPTIONS.get("DEDUP_HOURS", "")),
            "RSS_DOMAIN": (str(RSS_DOMAIN), DESCRIPTIONS.get("RSS_DOMAIN", "")),
            "RSS_SCHEME": (str(RSS_SCHEME), DESCRIPTIONS.get("RSS_SCHEME", ""))
        }
        
        # Écrase toutes les valeurs
        for key, (value, description) in configs.items():
            set_config(key, value, description)
        
        print(f"✅ {len(configs)} paramètres rechargés depuis .env")
        return len(configs)
        
    except Exception as e:
        print(f"⚠️  Erreur rechargement config: {e}")
        raise

def init_db():
    """Initialise la base de données avec toutes les tables"""
    conn = get_db_connection()
    try:
        # Table grabs
        conn.execute("""
        CREATE TABLE IF NOT EXISTS grabs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            prowlarr_id INTEGER UNIQUE,
            grabbed_at TEXT NOT NULL,
            title TEXT NOT NULL,
            torrent_url TEXT NOT NULL,
            torrent_file TEXT NOT NULL,
            title_hash TEXT,
            tracker TEXT,
            indexer_id INTEGER,
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
        
        # Index pour performances
        conn.execute("CREATE INDEX IF NOT EXISTS idx_grabs_date ON grabs(grabbed_at DESC)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_grabs_title_hash ON grabs(title_hash)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_grabs_prowlarr ON grabs(prowlarr_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_grabs_tracker ON grabs(tracker)")
        
        conn.commit()
        
        # Migration des colonnes si nécessaire
        migrate_db()
        
    finally:
        conn.close()

def migrate_db():
    """Effectue les migrations nécessaires"""
    conn = get_db_connection()
    try:
        cursor = conn.execute("PRAGMA table_info(grabs)")
        columns = [row[1] for row in cursor.fetchall()]
        
        # Ajout colonne title_hash si manquante
        if "title_hash" not in columns:
            print("🔄 Migration: Ajout colonne title_hash...")
            conn.execute("ALTER TABLE grabs ADD COLUMN title_hash TEXT")
            conn.commit()
        
        # Ajout colonne tracker si manquante
        if "tracker" not in columns:
            print("🔄 Migration: Ajout colonne tracker...")
            conn.execute("ALTER TABLE grabs ADD COLUMN tracker TEXT")
            conn.commit()
        
        # Ajout colonne indexer_id si manquante
        if "indexer_id" not in columns:
            print("🔄 Migration: Ajout colonne indexer_id...")
            conn.execute("ALTER TABLE grabs ADD COLUMN indexer_id INTEGER")
            conn.commit()
        
        # Remplir les hashes existants
        rows = conn.execute("SELECT id, title FROM grabs WHERE title_hash IS NULL").fetchall()
        for row_id, title in rows:
            title_hash = calculate_title_hash(title)
            conn.execute("UPDATE grabs SET title_hash = ? WHERE id = ?", (title_hash, row_id))
        
        conn.commit()
        print("✅ Migration complète")
        
        # Initialiser la config DB depuis .env si nécessaire
        init_config_from_env()
            
    except Exception as e:
        print(f"⚠️  Migration: {e}")
    finally:
        conn.close()

def calculate_title_hash(title: str) -> str:
    """Calcule le hash MD5 du titre (normalisé en lowercase)"""
    return hashlib.md5(title.lower().encode()).hexdigest()

def is_duplicate(title: str, dedup_hours: int) -> bool:
    """Vérifie si un grab avec le même titre existe dans la fenêtre de déduplication"""
    if dedup_hours <= 0:
        return False
    
    title_hash = calculate_title_hash(title)
    cutoff = (datetime.utcnow() - timedelta(hours=dedup_hours)).isoformat() + "Z"
    
    with get_db() as conn:
        result = conn.execute("""
        SELECT COUNT(*) FROM grabs
        WHERE title_hash = ? AND grabbed_at >= ?
        """, (title_hash, cutoff)).fetchone()
        
        return result[0] > 0

def insert_grab(grab_data: dict, torrent_file: str) -> Tuple[bool, str]:
    """Insère un grab dans la base de données"""
    with get_db() as conn:
        try:
            title_hash = calculate_title_hash(grab_data["title"])
            
            # Vérifier les doublons par prowlarr_id
            existing = conn.execute("""
            SELECT COUNT(*) FROM grabs WHERE prowlarr_id = ?
            """, (grab_data["prowlarr_id"],)).fetchone()
            
            if existing[0] > 0:
                return False, "Prowlarr ID existe déjà"
            
            conn.execute("""
            INSERT INTO grabs 
            (prowlarr_id, grabbed_at, title, torrent_url, torrent_file, title_hash, tracker, indexer_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                grab_data["prowlarr_id"],
                grab_data["date"],
                grab_data["title"],
                grab_data["torrent_url"],
                torrent_file,
                title_hash,
                grab_data.get("tracker"),
                grab_data.get("indexer_id")
            ))
            conn.commit()
            return True, "Grab inséré avec succès"
        except Exception as e:
            return False, str(e)

def get_grabs(limit: int = 50, dedup_hours: Optional[int] = None, tracker_filter: Optional[str] = None) -> List[dict]:
    """Récupère les derniers grabs avec déduplication optionnelle et filtre tracker"""
    with get_db() as conn:
        query = """
        SELECT id, prowlarr_id, grabbed_at, title, torrent_file, tracker
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

def get_stats(dedup_hours: Optional[int] = None) -> dict:
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
