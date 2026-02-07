# radarr_sonarr.py
from pathlib import Path
from typing import Optional
import hashlib
import logging

import bencodepy

logger = logging.getLogger(__name__)


def is_valid_torrent_file(file_path: str) -> bool:
    """
    Vérifie rapidement qu'un fichier semble être un torrent bencodé.
    Un torrent valide commence par 'd' (dictionnaire bencode).
    """
    try:
        path = Path(file_path)
        if not path.exists() or path.stat().st_size == 0:
            return False
        with path.open("rb") as fh:
            return fh.read(1) == b"d"
    except Exception:
        return False


def calculate_torrent_hash(torrent_file_path: str) -> Optional[str]:
    """
    Calcule l'info-hash SHA1 d'un fichier .torrent.
    Retourne None si le fichier est invalide.
    """
    try:
        if not is_valid_torrent_file(torrent_file_path):
            logger.warning("Fichier torrent invalide ou corrompu: %s", torrent_file_path)
            return None

        with open(torrent_file_path, "rb") as fh:
            torrent_data = bencodepy.decode(fh.read())
        info_dict = torrent_data.get(b"info")
        if info_dict is None:
            logger.warning("Fichier torrent sans clé 'info': %s", torrent_file_path)
            return None
        info_bytes = bencodepy.encode(info_dict)
        return hashlib.sha1(info_bytes).hexdigest().upper()
    except bencodepy.exceptions.BencodeDecodeError as exc:
        logger.warning("Erreur décodage torrent %s: %s", torrent_file_path, exc)
        return None
    except Exception as exc:
        logger.warning("Erreur calcul hash %s: %s", torrent_file_path, exc)
        return None
