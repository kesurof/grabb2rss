# prowlarr.py
import requests
from typing import Generator, Dict, Any

# Cache pour les trackers (indexerId -> nom du tracker)
_TRACKER_CACHE: Dict[int, str] = {}

def get_config_value(key: str, default: Any) -> Any:
    """Récupère une valeur de config depuis la DB ou .env"""
    try:
        from db import get_config
        from config import PROWLARR_URL, PROWLARR_API_KEY, PROWLARR_HISTORY_PAGE_SIZE
        
        # Valeurs par défaut depuis config.py
        defaults = {
            "PROWLARR_URL": PROWLARR_URL,
            "PROWLARR_API_KEY": PROWLARR_API_KEY,
            "PROWLARR_HISTORY_PAGE_SIZE": PROWLARR_HISTORY_PAGE_SIZE
        }
        
        # Essayer de lire depuis la DB (priorité)
        db_value = get_config(key)
        if db_value is not None:
            # Convertir en int si c'est PAGE_SIZE
            if key == "PROWLARR_HISTORY_PAGE_SIZE":
                return int(db_value)
            return db_value
        
        # Fallback sur .env
        return defaults.get(key, default)
    except Exception as e:
        print(f"⚠️  Erreur lecture config {key}: {e}")
        return default

def fetch_history() -> list:
    """Récupère l'historique Prowlarr avec config dynamique"""
    try:
        # Lire la config dynamiquement
        prowlarr_url = get_config_value("PROWLARR_URL", "http://localhost:9696")
        prowlarr_api_key = get_config_value("PROWLARR_API_KEY", "")
        page_size = get_config_value("PROWLARR_HISTORY_PAGE_SIZE", 100)
        
        response = requests.get(
            f"{prowlarr_url}/api/v1/history",
            headers={"X-Api-Key": prowlarr_api_key},
            params={"pageSize": page_size},
            timeout=10
        )
        response.raise_for_status()
        return response.json().get("records", [])
    except requests.RequestException as e:
        print(f"❌ Erreur Prowlarr: {e}")
        return []

def extract_tracker_name(record: dict) -> str:
    """Extrait le nom du tracker de plusieurs sources possibles avec cache"""
    
    indexer_id = record.get("indexerId")
    
    # Vérifier le cache en premier
    if indexer_id and indexer_id in _TRACKER_CACHE:
        return _TRACKER_CACHE[indexer_id]
    
    tracker_name = None
    
    # Méthode 1 : Essayer indexer.name
    if "indexer" in record and record["indexer"] and isinstance(record["indexer"], dict):
        if "name" in record["indexer"]:
            tracker_name = record["indexer"].get("name", "Unknown")
    
    # Méthode 2 : Essayer indexerName direct
    if not tracker_name and "indexerName" in record and record["indexerName"]:
        tracker_name = record["indexerName"]
    
    # Méthode 3 : Parser depuis data.indexerName
    if not tracker_name:
        data = record.get("data", {})
        if "indexerName" in data and data["indexerName"]:
            tracker_name = data["indexerName"]
    
    # Méthode 4 : Extraire depuis l'URL
    if not tracker_name:
        data = record.get("data", {})
        if "url" in data and data["url"]:
            try:
                from urllib.parse import urlparse
                parsed = urlparse(data["url"])
                # Extraire le domaine (ex: www.sharewood.tv -> sharewood.tv)
                domain = parsed.netloc
                # Supprimer www. si présent
                if domain.startswith("www."):
                    domain = domain[4:]
                # Capitaliser la première lettre
                tracker_name = domain.split('.')[0].capitalize()
            except Exception as e:
                print(f"⚠️  Erreur extraction URL: {e}")
    
    # Fallback
    if not tracker_name:
        tracker_name = "Unknown"
    
    # Mettre en cache si on a un indexer_id valide
    if indexer_id and tracker_name != "Unknown":
        _TRACKER_CACHE[indexer_id] = tracker_name
    
    return tracker_name

def extract_grabs(records: list) -> Generator[Dict[str, Any], None, None]:
    """Extrait les grabs releaseGrabbed réussis de l'historique avec tracker"""
    for record in records:
        # Filtrer par eventType ET successful
        if record.get("eventType") == "releaseGrabbed" and record.get("successful") == True:
            try:
                data = record.get("data", {})
                
                yield {
                    "prowlarr_id": record.get("id"),
                    "date": record.get("date"),
                    "title": data.get("grabTitle"),
                    "torrent_url": data.get("url"),
                    "tracker": extract_tracker_name(record),
                    "indexer_id": record.get("indexerId")
                }
            except Exception as e:
                print(f"❌ Erreur extraction grab: {e}")
                continue
