# rss.py
from xml.etree.ElementTree import Element, SubElement, tostring
from datetime import datetime
from typing import Optional
from urllib.parse import quote, urlencode

from db import get_db_connection, resolve_torrent_path
import logging
from config import (
    RSS_TITLE, RSS_DESCRIPTION, RSS_DOMAIN, RSS_SCHEME,
    RSS_INTERNAL_URL, TORRENT_DIR, RSS_ALLOWED_HOSTS
)

logger = logging.getLogger(__name__)

def is_docker_internal_request(request_host: Optional[str]) -> bool:
    """
    Détermine si la requête provient de l'intérieur du réseau Docker

    Args:
        request_host: Host de la requête

    Returns:
        True si requête interne Docker, False sinon
    """
    if not request_host:
        return False

    # Détection stricte: hôte exact (avec/sans port), jamais par sous-chaîne.
    host_normalized = request_host.strip().lower()
    host_no_port = _host_without_port(request_host)

    internal_hosts = {
        "grabb2rss",  # Nom de service Docker
        "grab2rss",   # Alias historique
        "localhost",
        "127.0.0.1",
        "::1",
        "0.0.0.0",
    }

    return host_normalized in internal_hosts or host_no_port in internal_hosts

def get_torrent_url(base_url: str, torrent_file: str, api_key: Optional[str] = None) -> str:
    """Génère une URL encodée pour le téléchargement torrent."""
    encoded_file = quote(torrent_file, safe='')
    url = f"{base_url}/api/torrents/download/{encoded_file}"
    if api_key:
        url = f"{url}?{urlencode({'apikey': api_key})}"
    return url


def _normalize_host(host: str) -> str:
    return host.strip().lower()


def _host_without_port(host: str) -> str:
    host = host.strip()
    if host.startswith("["):
        end = host.find("]")
        if end != -1:
            return host[1:end].lower()
    if ":" in host:
        name, port = host.rsplit(":", 1)
        if port.isdigit():
            return name.lower()
    return host.lower()


def _is_allowed_host(request_host: str) -> bool:
    if not request_host:
        return False
    normalized = _normalize_host(request_host)
    normalized_no_port = _host_without_port(request_host)
    allowed = [h.strip().lower() for h in RSS_ALLOWED_HOSTS if str(h).strip()]
    if normalized == RSS_DOMAIN.lower() or normalized_no_port == RSS_DOMAIN.lower():
        return True
    return normalized in allowed or normalized_no_port in allowed

def generate_rss(
    request_host: Optional[str] = None,
    request_scheme: Optional[str] = None,
    tracker_filter: Optional[str] = None,
    limit: int = 100,
    api_key: Optional[str] = None,
) -> bytes:
    """
    Génère le flux RSS multi-client avec filtres optionnels

    Compatible avec rutorrent, qBittorrent, Transmission

    Logique de sélection d'URL:
    - Si requête interne Docker (grabb2rss, localhost, etc.) → utilise RSS_INTERNAL_URL
    - Sinon → utilise domaine public (RSS_SCHEME://RSS_DOMAIN)

    Args:
        request_host: Host de la requête
        tracker_filter: Filtre par tracker (None = tous)
        limit: Nombre d'items max
    """

    # Déterminer la base URL selon le contexte
    effective_scheme = (request_scheme or RSS_SCHEME or "http").strip().lower()
    if effective_scheme not in {"http", "https"}:
        effective_scheme = RSS_SCHEME

    if is_docker_internal_request(request_host):
        # Requête depuis l'intérieur de Docker (ex: qBittorrent dans un autre conteneur)
        base_url = RSS_INTERNAL_URL
    elif request_host and _is_allowed_host(request_host):
        # Requête externe avec host spécifique
        base_url = f"{effective_scheme}://{request_host}"
    else:
        if request_host and not _is_allowed_host(request_host):
            logger.warning("Host RSS non autorisé: %s (fallback vers RSS_DOMAIN)", request_host)
        # Fallback sur domaine public configuré
        base_url = f"{RSS_SCHEME}://{RSS_DOMAIN}"
    
    rss = Element("rss", version="2.0")
    rss.set("xmlns:content", "http://purl.org/rss/1.0/modules/content/")
    
    channel = SubElement(rss, "channel")
    
    # Titre avec filtre
    title = RSS_TITLE
    if tracker_filter:
        title += f" - {tracker_filter}"
    
    SubElement(channel, "title").text = title
    SubElement(channel, "link").text = base_url
    SubElement(channel, "description").text = RSS_DESCRIPTION
    SubElement(channel, "language").text = "fr"

    conn = get_db_connection()
    try:
        # Récupérer la date du dernier grab pour lastBuildDate
        if tracker_filter:
            latest_grab = conn.execute("""
                SELECT grabbed_at FROM grabs
                WHERE tracker = ?
                ORDER BY grabbed_at DESC LIMIT 1
            """, (tracker_filter,)).fetchone()
        else:
            latest_grab = conn.execute("""
                SELECT grabbed_at FROM grabs
                ORDER BY grabbed_at DESC LIMIT 1
            """).fetchone()

        # Utiliser la date du dernier grab ou la date actuelle si aucun grab
        last_build_date = latest_grab[0] if latest_grab else datetime.utcnow().isoformat() + "Z"
        SubElement(channel, "lastBuildDate").text = last_build_date
        SubElement(channel, "ttl").text = "30"

        # Requête avec ou sans filtre tracker
        if tracker_filter:
            query = """
            SELECT id, grabbed_at, title, torrent_file, tracker
            FROM grabs
            WHERE tracker = ?
            ORDER BY grabbed_at DESC
            LIMIT ?
            """
            rows = conn.execute(query, (tracker_filter, limit)).fetchall()
        else:
            query = """
            SELECT id, grabbed_at, title, torrent_file, tracker
            FROM grabs
            ORDER BY grabbed_at DESC
            LIMIT ?
            """
            rows = conn.execute(query, (limit,)).fetchall()
        
        for grab_id, grabbed_at, title, torrent_file, tracker in rows:
            item = SubElement(channel, "item")
            
            SubElement(item, "title").text = title
            SubElement(item, "pubDate").text = grabbed_at
            SubElement(item, "guid", isPermaLink="false").text = f"grab-{grab_id}"
            
            description = f"Torrent: {title}"
            if tracker:
                description += f" | Tracker: {tracker}"
            SubElement(item, "description").text = description
            
            # URLs avec encoding
            torrent_url = get_torrent_url(base_url, torrent_file, api_key=api_key)
            SubElement(item, "link").text = torrent_url
            
            # Enclosure pour rutorrent, qBittorrent, Transmission
            enclosure = SubElement(item, "enclosure")
            enclosure.set("url", torrent_url)
            enclosure.set("type", "application/x-bittorrent")
            
            # Déterminer la taille du fichier
            try:
                torrent_path = resolve_torrent_path(torrent_file)
                if torrent_path and torrent_path.exists():
                    size = torrent_path.stat().st_size
                    enclosure.set("length", str(size))
            except Exception:
                pass
            
            # Content
            SubElement(item, "content:encoded").text = f"<![CDATA[{title}]]>"
    
    finally:
        conn.close()
    
    return tostring(rss, encoding="utf-8", xml_declaration=True)

def generate_torrent_json(
    request_host: Optional[str] = None,
    request_scheme: Optional[str] = None,
    tracker_filter: Optional[str] = None,
    limit: int = 100,
    api_key: Optional[str] = None,
) -> dict:
    """Génère un flux au format JSON avec filtres"""

    # Déterminer la base URL selon le contexte
    effective_scheme = (request_scheme or RSS_SCHEME or "http").strip().lower()
    if effective_scheme not in {"http", "https"}:
        effective_scheme = RSS_SCHEME

    if is_docker_internal_request(request_host):
        # Requête depuis l'intérieur de Docker (ex: qBittorrent dans un autre conteneur)
        base_url = RSS_INTERNAL_URL
    elif request_host and _is_allowed_host(request_host):
        # Requête externe avec host spécifique
        base_url = f"{effective_scheme}://{request_host}"
    else:
        if request_host and not _is_allowed_host(request_host):
            logger.warning("Host RSS non autorisé: %s (fallback vers RSS_DOMAIN)", request_host)
        # Fallback sur domaine public configuré
        base_url = f"{RSS_SCHEME}://{RSS_DOMAIN}"
    
    conn = get_db_connection()
    try:
        if tracker_filter:
            query = """
            SELECT id, grabbed_at, title, torrent_file, tracker
            FROM grabs
            WHERE tracker = ?
            ORDER BY grabbed_at DESC
            LIMIT ?
            """
            rows = conn.execute(query, (tracker_filter, limit)).fetchall()
        else:
            query = """
            SELECT id, grabbed_at, title, torrent_file, tracker
            FROM grabs
            ORDER BY grabbed_at DESC
            LIMIT ?
            """
            rows = conn.execute(query, (limit,)).fetchall()
        
        items = []
        for grab_id, grabbed_at, title, torrent_file, tracker in rows:
            torrent_url = get_torrent_url(base_url, torrent_file, api_key=api_key)
            items.append({
                "id": f"grab-{grab_id}",
                "title": title,
                "pubDate": grabbed_at,
                "link": torrent_url,
                "torrent": torrent_url,
                "tracker": tracker,
                "magnetLink": None
            })
        
        name = RSS_TITLE
        if tracker_filter:
            name += f" - {tracker_filter}"
        
        return {
            "version": "0.1",
            "name": name,
            "description": RSS_DESCRIPTION,
            "items": items
        }
    
    finally:
        conn.close()
