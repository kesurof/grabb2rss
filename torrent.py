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

def is_valid_torrent_content(content: bytes) -> bool:
    """
    Vérifie si le contenu téléchargé est un torrent valide
    Un fichier torrent bencodé commence toujours par 'd' (dictionnaire)
    """
    if not content or len(content) < 1:
        return False
    
    # Un fichier torrent commence par 'd' en bencode
    # Si ça commence par '<', c'est du HTML (erreur 404, etc.)
    return content[0:1] == b'd'

def download_torrent(title: str, url: str) -> str:
    """Télécharge et sauvegarde le fichier torrent - Retourne SEULEMENT le nom du fichier"""
    filename = safe_filename(f"{title}.torrent")
    path = TORRENT_DIR / filename
    
    # Si le fichier existe déjà, retourner SEULEMENT le nom
    if path.exists():
        return filename
    
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        
        # Vérifier que le contenu est un torrent valide
        content = response.content
        if not is_valid_torrent_content(content):
            # Détecter si c'est du HTML
            if content[0:1] == b'<':
                raise ValueError(
                    f"Le fichier téléchargé est du HTML (erreur 404, page tracker, etc.), pas un torrent. "
                    f"URL: {url[:100]}"
                )
            else:
                raise ValueError(
                    f"Le fichier téléchargé n'est pas un torrent valide (ne commence pas par 'd'). "
                    f"Premier octet: {content[0:1]}"
                )
        
        with open(path, "wb") as f:
            f.write(content)
        
        # Retourner SEULEMENT le nom du fichier (pas le chemin complet)
        return filename
    except requests.RequestException as e:
        print(f"❌ Erreur download torrent {title}: {e}")
        raise
    except ValueError as e:
        print(f"❌ Fichier invalide {title}: {e}")
        raise
