# rss.py
from xml.etree.ElementTree import Element, SubElement, tostring
from datetime import datetime
from pathlib import Path
from typing import Optional
from urllib.parse import quote

from db import get_db_connection
from config import RSS_TITLE, RSS_DESCRIPTION, RSS_DOMAIN, RSS_SCHEME, RSS_INTERNAL_URL, TORRENT_DIR

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

    # Normaliser en minuscules pour comparaison
    host_lower = request_host.lower()

    # Indicateurs d'accès interne Docker
    internal_indicators = [
        'grabb2rss',       # Nom du service Docker
        'grab2rss',        # Alias possible
        'localhost',       # Accès local
        '127.0.0.1',       # Loopback IPv4
        '::1',             # Loopback IPv6
        '0.0.0.0'          # Wildcard
    ]

    return any(indicator in host_lower for indicator in internal_indicators)

def get_torrent_url(base_url: str, torrent_file: str) -> str:
    """Génère une URL encodée pour le fichier torrent"""
    encoded_file = quote(torrent_file, safe='')
    return f"{base_url}/torrents/{encoded_file}"

def generate_rss(
    request_host: Optional[str] = None,
    tracker_filter: Optional[str] = None,
    limit: int = 100
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
    if is_docker_internal_request(request_host):
        # Requête depuis l'intérieur de Docker (ex: qBittorrent dans un autre conteneur)
        base_url = RSS_INTERNAL_URL
    elif request_host:
        # Requête externe avec host spécifique
        base_url = f"{RSS_SCHEME}://{request_host}"
    else:
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
    SubElement(channel, "lastBuildDate").text = datetime.utcnow().isoformat() + "Z"
    SubElement(channel, "ttl").text = "30"
    
    conn = get_db_connection()
    try:
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
            torrent_url = get_torrent_url(base_url, torrent_file)
            SubElement(item, "link").text = torrent_url
            
            # Enclosure pour rutorrent, qBittorrent, Transmission
            enclosure = SubElement(item, "enclosure")
            enclosure.set("url", torrent_url)
            enclosure.set("type", "application/x-bittorrent")
            
            # Déterminer la taille du fichier
            try:
                torrent_path = TORRENT_DIR / torrent_file
                if torrent_path.exists():
                    size = torrent_path.stat().st_size
                    enclosure.set("length", str(size))
            except:
                pass
            
            # Content
            SubElement(item, "content:encoded").text = f"<![CDATA[{title}]]>"
    
    finally:
        conn.close()
    
    return tostring(rss, encoding="utf-8", xml_declaration=True)

def generate_torrent_json(
    request_host: Optional[str] = None,
    tracker_filter: Optional[str] = None,
    limit: int = 100
) -> dict:
    """Génère un flux au format JSON avec filtres"""

    # Déterminer la base URL selon le contexte
    if is_docker_internal_request(request_host):
        # Requête depuis l'intérieur de Docker (ex: qBittorrent dans un autre conteneur)
        base_url = RSS_INTERNAL_URL
    elif request_host:
        # Requête externe avec host spécifique
        base_url = f"{RSS_SCHEME}://{request_host}"
    else:
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
            torrent_url = get_torrent_url(base_url, torrent_file)
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
