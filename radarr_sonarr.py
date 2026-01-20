# radarr_sonarr.py
"""
Module pour vérifier si les grabs Prowlarr ont été importés dans Radarr/Sonarr
Utilise les downloadId pour faire le lien entre grabbed et downloadFolderImported
"""
import requests
from typing import Set, Optional
from datetime import datetime
from pathlib import Path

# Import de TORRENT_DIR pour reconstruire les chemins
from config import TORRENT_DIR

# Cache des downloadId importés (rafraîchi toutes les 5 minutes)
_imported_cache = {}
_cache_timestamp = None
CACHE_DURATION = 300  # 5 minutes en secondes

def get_radarr_imported_download_ids(radarr_url: str, radarr_api_key: str, page_size: int = 200) -> Set[str]:
    """
    Récupère les downloadId qui ont été grabbed (choisis pour téléchargement) par Radarr

    CORRIGÉ v2.6: Retourne tous les torrents grabbed, peu importe leur statut d'import
    Un torrent "grabbed" = Radarr a décidé de le télécharger (même s'il n'est pas encore importé)

    Stratégie:
    1. Récupérer tous les grabbed avec leur downloadId
    2. Récupérer tous les downloadFolderImported (pour stats uniquement)
    3. Retourner tous les grabbed (pas seulement ceux importés)
    """
    try:
        response = requests.get(
            f"{radarr_url}/api/v3/history",
            headers={"X-Api-Key": radarr_api_key},
            params={"pageSize": page_size},
            timeout=10
        )
        response.raise_for_status()
        data = response.json()
        
        # Extraire les downloadId des grabbed
        grabbed_ids = set()
        for record in data.get("records", []):
            if record.get("eventType") == "grabbed":
                download_id = record.get("downloadId")
                if download_id:
                    grabbed_ids.add(download_id)

        # Extraire les downloadId des downloadFolderImported (pour stats uniquement)
        imported_ids = set()
        for record in data.get("records", []):
            if record.get("eventType") == "downloadFolderImported":
                download_id = record.get("downloadId")
                if download_id:
                    imported_ids.add(download_id)

        # CORRIGÉ: On garde tous les grabbed, peu importe s'ils sont importés ou non
        # Un torrent "grabbed" = choisi par Radarr pour téléchargement
        valid_ids = grabbed_ids

        print(f"📥 Radarr: {len(grabbed_ids)} grabbed, {len(imported_ids)} imported, {len(valid_ids)} valides")
        return valid_ids
        
    except Exception as e:
        print(f"⚠️  Erreur Radarr API: {e}")
        return set()

def get_sonarr_imported_download_ids(sonarr_url: str, sonarr_api_key: str, page_size: int = 200) -> Set[str]:
    """
    Récupère les downloadId qui ont été grabbed (choisis pour téléchargement) par Sonarr

    CORRIGÉ v2.6: Retourne tous les torrents grabbed, peu importe leur statut d'import
    Un torrent "grabbed" = Sonarr a décidé de le télécharger (même s'il n'est pas encore importé)
    """
    try:
        response = requests.get(
            f"{sonarr_url}/api/v3/history",
            headers={"X-Api-Key": sonarr_api_key},
            params={"pageSize": page_size},
            timeout=10
        )
        response.raise_for_status()
        data = response.json()
        
        # Extraire les downloadId des grabbed
        grabbed_ids = set()
        for record in data.get("records", []):
            if record.get("eventType") == "grabbed":
                download_id = record.get("downloadId")
                if download_id:
                    grabbed_ids.add(download_id)

        # Extraire les downloadId des downloadFolderImported (pour stats uniquement)
        imported_ids = set()
        for record in data.get("records", []):
            if record.get("eventType") == "downloadFolderImported":
                download_id = record.get("downloadId")
                if download_id:
                    imported_ids.add(download_id)

        # CORRIGÉ: On garde tous les grabbed, peu importe s'ils sont importés ou non
        # Un torrent "grabbed" = choisi par Sonarr pour téléchargement
        valid_ids = grabbed_ids

        print(f"📺 Sonarr: {len(grabbed_ids)} grabbed, {len(imported_ids)} imported, {len(valid_ids)} valides")
        return valid_ids
        
    except Exception as e:
        print(f"⚠️  Erreur Sonarr API: {e}")
        return set()

def get_all_imported_download_ids(
    radarr_url: Optional[str] = None,
    radarr_api_key: Optional[str] = None,
    sonarr_url: Optional[str] = None,
    sonarr_api_key: Optional[str] = None,
    use_cache: bool = True
) -> Set[str]:
    """
    Récupère tous les downloadId grabbed (choisis) depuis Radarr et Sonarr

    CORRIGÉ v2.6: Retourne les torrents grabbed, pas seulement ceux importés
    Cela permet d'inclure les téléchargements en cours dans le flux RSS

    Avec cache de 5 minutes pour éviter de surcharger les APIs
    """
    global _imported_cache, _cache_timestamp
    
    # Vérifier le cache
    if use_cache and _cache_timestamp:
        elapsed = (datetime.utcnow() - _cache_timestamp).total_seconds()
        if elapsed < CACHE_DURATION:
            print(f"💾 Utilisation du cache ({int(CACHE_DURATION - elapsed)}s restantes)")
            return _imported_cache
    
    # Récupérer les downloadId
    all_ids = set()
    
    if radarr_url and radarr_api_key:
        radarr_ids = get_radarr_imported_download_ids(radarr_url, radarr_api_key)
        all_ids.update(radarr_ids)
    
    if sonarr_url and sonarr_api_key:
        sonarr_ids = get_sonarr_imported_download_ids(sonarr_url, sonarr_api_key)
        all_ids.update(sonarr_ids)
    
    # Mettre à jour le cache
    _imported_cache = all_ids
    _cache_timestamp = datetime.utcnow()
    
    print(f"✅ Total: {len(all_ids)} downloadId importés dans le cache")
    return all_ids

def extract_download_id_from_url(torrent_url: str) -> Optional[str]:
    """
    Extrait un downloadId depuis l'URL du torrent
    Le downloadId est généralement le hash du torrent (SHA1)
    
    Exemples d'URL:
    - https://www.sharewood.tv/api/.../29822/download
    - magnet:?xt=urn:btih:54287C2DD24CEE34D87DF8F59FA8C2F578C551B9
    """
    import re
    from urllib.parse import urlparse, parse_qs
    
    # Cas 1: Magnet link
    if torrent_url.startswith("magnet:"):
        match = re.search(r'btih:([a-fA-F0-9]{40})', torrent_url)
        if match:
            return match.group(1).upper()
    
    # Cas 2: Hash dans l'URL
    match = re.search(r'([a-fA-F0-9]{40})', torrent_url)
    if match:
        return match.group(1).upper()
    
    return None

def is_valid_torrent_file(file_path: str) -> bool:
    """
    Vérifie si un fichier est un torrent valide avant de le parser
    Un fichier torrent bencodé commence toujours par 'd' (dictionnaire)
    """
    try:
        path = Path(file_path)
        if not path.exists() or path.stat().st_size == 0:
            return False
        
        with open(file_path, 'rb') as f:
            first_byte = f.read(1)
            # Un fichier torrent bencodé commence toujours par 'd'
            # Si ça commence par '<', c'est du HTML (erreur 404, etc.)
            if first_byte != b'd':
                return False
        
        return True
    except Exception:
        return False

def calculate_torrent_hash(torrent_file_path: str) -> Optional[str]:
    """
    Calcule le hash SHA1 (info_hash) d'un fichier .torrent
    C'est ce hash qui est utilisé comme downloadId par Radarr/Sonarr
    
    CORRIGÉ v2.5: Vérifie que le fichier est un torrent valide avant parsing
    """
    try:
        # Vérification préalable du fichier
        if not is_valid_torrent_file(torrent_file_path):
            print(f"⚠️  Fichier torrent invalide ou corrompu: {torrent_file_path}")
            return None
        
        import hashlib
        import bencodepy
        
        with open(torrent_file_path, 'rb') as f:
            torrent_data = bencodepy.decode(f.read())
            
            # Vérifier que 'info' existe
            if b'info' not in torrent_data:
                print(f"⚠️  Fichier torrent sans clé 'info': {torrent_file_path}")
                return None
            
            info = bencodepy.encode(torrent_data[b'info'])
            info_hash = hashlib.sha1(info).hexdigest().upper()
            return info_hash
            
    except bencodepy.exceptions.BencodeDecodeError as e:
        print(f"⚠️  Erreur décodage torrent {torrent_file_path}: {e}")
        # Le fichier n'est probablement pas un torrent valide (HTML, page d'erreur, etc.)
        print(f"💡 Le fichier téléchargé n'est pas un torrent valide. Vérifiez l'URL source.")
        return None
    except Exception as e:
        print(f"⚠️  Erreur inattendue calcul hash {torrent_file_path}: {e}")
        return None

def is_download_id_imported(torrent_file: str, imported_download_ids: Set[str]) -> bool:
    """
    Vérifie si le downloadId du fichier .torrent a été importé dans Radarr/Sonarr
    
    Args:
        torrent_file: Nom du fichier torrent OU chemin complet
        imported_download_ids: Set des downloadId importés
    
    CORRIGÉ v2.5.1: Accepte maintenant seulement le nom de fichier (reconstruit le chemin)
    """
    # Si c'est juste un nom de fichier (pas de slash), reconstruire le chemin complet
    if '/' not in torrent_file and '\\' not in torrent_file:
        torrent_file_path = str(TORRENT_DIR / torrent_file)
    else:
        torrent_file_path = torrent_file
    
    # Calculer le hash du .torrent
    download_id = calculate_torrent_hash(torrent_file_path)
    
    if not download_id:
        # Si on ne peut pas calculer le hash, on ne peut pas vérifier
        # On retourne False pour être strict (le fichier n'est pas un torrent valide)
        return False
    
    return download_id in imported_download_ids

def clear_cache():
    """Vide le cache (utile pour forcer un refresh)"""
    global _imported_cache, _cache_timestamp
    _imported_cache = {}
    _cache_timestamp = None
    print("🗑️  Cache Radarr/Sonarr vidé")

def get_cache_info() -> dict:
    """Retourne des informations sur le cache"""
    global _imported_cache, _cache_timestamp
    
    if not _cache_timestamp:
        return {
            "cached": False,
            "count": 0,
            "age_seconds": None
        }
    
    age = (datetime.utcnow() - _cache_timestamp).total_seconds()
    
    return {
        "cached": True,
        "count": len(_imported_cache),
        "age_seconds": int(age),
        "expires_in_seconds": int(max(0, CACHE_DURATION - age))
    }
