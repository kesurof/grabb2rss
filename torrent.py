# torrent.py
import os
import requests
from pathlib import Path
from config import TORRENT_DIR

def safe_filename(name: str) -> str:
    """Nettoie le nom de fichier pour éviter les caractères interdits"""
    return (
        name.replace("/", "_")
        .replace("\\", "_")
        .replace(":", "")
        .replace("?", "")
        .replace("*", "")
        .replace('"', "")
        .replace("<", "")
        .replace(">", "")
        .replace("|", "")
        .strip()[:200]
    )

def download_torrent(title: str, url: str) -> str:
    """Télécharge et sauvegarde le fichier torrent"""
    filename = safe_filename(f"{title}.torrent")
    path = TORRENT_DIR / filename
    
    # Si le fichier existe déjà, on le retourne (chemin complet)
    if path.exists():
        return str(path)
    
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        
        with open(path, "wb") as f:
            f.write(response.content)
        
        # Retourner le chemin complet au lieu du nom
        return str(path)
    except requests.RequestException as e:
        print(f"❌ Erreur download torrent {title}: {e}")
        raise
