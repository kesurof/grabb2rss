# prowlarr.py
import requests
import logging
from typing import Generator, Dict, Any
from network import request_with_retries

# Cache pour les trackers (indexerId -> nom du tracker)
_TRACKER_CACHE: Dict[int, str] = {}
logger = logging.getLogger(__name__)

def fetch_history() -> list:
    """Récupère l'historique Prowlarr avec config depuis config.py"""
    try:
        # Lire la config depuis config.py (qui charge settings.yml)
        from config import PROWLARR_URL, PROWLARR_API_KEY

        prowlarr_url = PROWLARR_URL
        prowlarr_api_key = PROWLARR_API_KEY
        page_size = 500
        
        response = request_with_retries(
            "GET",
            f"{prowlarr_url}/api/v1/history",
            headers={"X-Api-Key": prowlarr_api_key},
            params={"pageSize": page_size}
        )
        return response.json().get("records", [])
    except requests.RequestException as e:
        logger.error("Erreur Prowlarr: %s", e)
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
                logger.warning("Erreur extraction URL tracker: %s", e)
    
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
                logger.warning("Erreur extraction grab: %s", e)
                continue

def clear_tracker_cache():
    """Vide le cache des trackers"""
    global _TRACKER_CACHE
    count = len(_TRACKER_CACHE)
    _TRACKER_CACHE.clear()
    logger.info("Cache trackers vidé (%s entrées)", count)
    return count

def get_tracker_cache_info() -> dict:
    """Retourne des informations sur le cache des trackers"""
    return {
        "count": len(_TRACKER_CACHE),
        "trackers": list(_TRACKER_CACHE.values())
    }
