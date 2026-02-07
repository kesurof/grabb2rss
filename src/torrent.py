# torrent.py
import requests
import logging
from config import TORRENT_DIR, TORRENTS_MAX_SIZE_MB

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

logger = logging.getLogger(__name__)

def download_torrent(title: str, url: str) -> str:
    """Télécharge et sauvegarde le fichier torrent - Retourne SEULEMENT le nom du fichier"""
    filename = safe_filename(f"{title}.torrent")
    path = TORRENT_DIR / filename
    
    # Si le fichier existe déjà, retourner SEULEMENT le nom
    if path.exists():
        return filename
    
    try:
        response = requests.get(url, timeout=30, stream=True)
        response.raise_for_status()

        max_size_bytes = max(int(TORRENTS_MAX_SIZE_MB), 1) * 1024 * 1024
        bytes_written = 0
        first_chunk = b""

        with path.open("wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                if not chunk:
                    continue
                if not first_chunk:
                    first_chunk = chunk[:1]
                    if first_chunk != b'd':
                        if first_chunk == b'<':
                            raise ValueError(
                                "Le fichier téléchargé est du HTML (erreur 404, page tracker, etc.), pas un torrent."
                            )
                        raise ValueError(
                            "Le fichier téléchargé n'est pas un torrent valide (ne commence pas par 'd')."
                        )

                bytes_written += len(chunk)
                if bytes_written > max_size_bytes:
                    raise ValueError(
                        f"Le fichier torrent dépasse la taille max ({TORRENTS_MAX_SIZE_MB} MB)."
                    )
                f.write(chunk)

        # Vérification finale basique
        if not is_valid_torrent_content(first_chunk):
            raise ValueError("Le fichier torrent est invalide (contenu inattendu).")
        
        # Retourner SEULEMENT le nom du fichier (pas le chemin complet)
        return filename
    except (requests.RequestException, ValueError) as e:
        logger.error("Erreur téléchargement torrent %s: %s", title, e)
        try:
            path.unlink(missing_ok=True)
        except Exception:
            pass
        raise
