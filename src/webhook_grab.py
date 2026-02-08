# webhook_grab.py
import logging
from urllib.parse import quote
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from network import request_with_retries
from torrent import download_torrent, safe_filename
from db import insert_grab, upsert_grab_history
from radarr_sonarr import calculate_torrent_hash
from config import TORRENT_DIR
import secrets

logger = logging.getLogger(__name__)


def _normalize_indexer(value: Optional[str]) -> str:
    if not value:
        return ""
    text = value.strip()
    text = text.replace("(Prowlarr)", "").replace("(API)", "").strip()
    return " ".join(text.split()).lower()


def _size_matches(candidate_size: Optional[int], target_size: Optional[int]) -> bool:
    try:
        cand = int(candidate_size) if candidate_size is not None else None
    except (TypeError, ValueError):
        cand = None
    try:
        target = int(target_size) if target_size is not None else None
    except (TypeError, ValueError):
        target = None

    if not cand or not target:
        return False
    tolerance = max(int(target * 0.02), 5 * 1024 * 1024)
    return abs(cand - target) <= tolerance


def _score_candidate(
    candidate: Dict[str, Any],
    download_id: str,
    release_title: str,
    indexer_name: Optional[str],
    release_size: Optional[int],
) -> int:
    score = 0
    cand_title = candidate.get("title") or ""
    cand_indexer = candidate.get("indexer") or ""

    if release_title and cand_title.lower() == release_title.lower():
        score += 2
    elif release_title and release_title.lower() in cand_title.lower():
        score += 1

    if indexer_name and _normalize_indexer(indexer_name) == _normalize_indexer(cand_indexer):
        score += 1

    cand_hash = (candidate.get("infoHash") or candidate.get("infoHashV1")
                 or candidate.get("downloadId") or candidate.get("hash") or "")
    if download_id and cand_hash and cand_hash.lower() == download_id.lower():
        score += 3

    if _size_matches(candidate.get("size"), release_size):
        score += 1

    return score


def _resolve_indexer_id(prowlarr_url: str, prowlarr_api_key: str, indexer_name: str) -> Optional[int]:
    if not indexer_name:
        return None
    try:
        response = request_with_retries(
            "GET",
            f"{prowlarr_url.rstrip('/')}/api/v1/indexer",
            headers={"X-Api-Key": prowlarr_api_key}
        )
        data = response.json() if response.ok else []
        if not isinstance(data, list):
            return None
        target = _normalize_indexer(indexer_name)
        for item in data:
            name = item.get("name") or ""
            if _normalize_indexer(name) == target:
                return item.get("id")
    except Exception as exc:
        logger.warning("Prowlarr indexers: erreur %s", exc)
    return None


def _download_via_indexer(
    prowlarr_url: str,
    prowlarr_api_key: str,
    info_url: str,
    indexer_name: str,
    title: str
) -> Optional[Dict[str, Any]]:
    indexer_id = _resolve_indexer_id(prowlarr_url, prowlarr_api_key, indexer_name)
    if not indexer_id:
        return None
    filename = safe_filename(f"{title}.torrent")
    base = prowlarr_url.rstrip("/")
    download_url = (
        f"{base}/api/v1/indexer/{indexer_id}/download"
        f"?link={quote(info_url, safe='')}&file={quote(filename, safe='')}"
    )
    torrent_file = download_torrent(title, download_url)
    return {"torrent_file": torrent_file, "download_url": download_url, "indexer_id": indexer_id}


def generate_webhook_token() -> str:
    return secrets.token_urlsafe(32)


def _insert_minimal_grab(
    *,
    instance_name: str,
    source: str,
    release_title: str,
    download_id: str,
    indexer_name: Optional[str],
    fallback_url: Optional[str]
) -> Dict[str, Any]:
    """Insère un grab canonique minimal (sans .torrent) pour unifier l'ingestion."""
    grab_data = {
        "prowlarr_id": None,
        "download_id": download_id or None,
        "instance": instance_name or "unknown",
        "source": source or "history",
        "date": datetime.now(timezone.utc).isoformat(),
        "title": release_title,
        "torrent_url": fallback_url or "",
        "tracker": indexer_name,
        "indexer_id": None
    }
    success, message = insert_grab(grab_data, "")
    if not success:
        return {"status": "error", "reason": message}
    return {"status": "ok", "mode": "minimal", "downloadUrl": fallback_url}


def ingest_grab_event(
    *,
    instance_name: str,
    source: str,
    release_title: str,
    download_id: str = "",
    indexer_name: Optional[str] = None,
    release_size: Optional[int] = None,
    info_url: Optional[str] = None,
    prowlarr_url: str,
    prowlarr_api_key: str,
    min_score: int = 3,
    strict: bool = True,
    download: bool = True,
    allow_download_for_history: bool = False,
    allow_missing_candidate: bool = False,
) -> Dict[str, Any]:
    """Service unique d'ingestion grab (webhook + history)."""
    if not release_title:
        return {"status": "error", "reason": "missing releaseTitle"}

    logger.info(
        "Ingestion grab: source=%s instance=%s title=%s downloadId=%s",
        source,
        instance_name,
        release_title,
        download_id[:12] + "…" if download_id else "n/a"
    )

    results: list = []
    if prowlarr_url and prowlarr_api_key:
        try:
            search_url = f"{prowlarr_url.rstrip('/')}/api/v1/search"
            response = request_with_retries(
                "GET",
                search_url,
                headers={"X-Api-Key": prowlarr_api_key},
                params={"query": release_title}
            )
            candidate_results = response.json() if response.ok else []
            if isinstance(candidate_results, list):
                results = candidate_results
        except Exception as exc:
            logger.warning("Ingestion search erreur: %s", exc)
    else:
        logger.warning("Ingestion search ignorée: Prowlarr non configuré")

    logger.info("Ingestion Prowlarr search: %s résultat(s)", len(results))
    effective_download = bool(download and (source != "history_sync" or allow_download_for_history))
    if download and not effective_download and source == "history_sync":
        logger.info("History sync: téléchargement .torrent désactivé (mode non explicite)")

    scored = []
    for cand in results:
        scored.append({
            "score": _score_candidate(cand, download_id, release_title, indexer_name, release_size),
            "candidate": cand
        })
    scored.sort(key=lambda x: x["score"], reverse=True)

    # Mode réconciliation: garder la donnée même sans match Prowlarr.
    if not scored:
        if allow_missing_candidate:
            minimal = _insert_minimal_grab(
                instance_name=instance_name,
                source=source,
                release_title=release_title,
                download_id=download_id,
                indexer_name=indexer_name,
                fallback_url=info_url
            )
            minimal["fallback_used"] = False
            minimal["indexer"] = indexer_name
            return minimal
        return {"status": "error", "reason": "no candidates"}

    best = scored[0]["candidate"]
    best_score = scored[0]["score"]
    if best_score < min_score:
        if allow_missing_candidate:
            minimal = _insert_minimal_grab(
                instance_name=instance_name,
                source=source,
                release_title=release_title,
                download_id=download_id,
                indexer_name=indexer_name,
                fallback_url=info_url or best.get("downloadUrl")
            )
            minimal["score"] = best_score
            minimal["fallback_used"] = False
            minimal["indexer"] = indexer_name
            return minimal
        return {"status": "error", "reason": "score too low", "score": best_score}

    download_url = best.get("downloadUrl")
    if not download_url and not allow_missing_candidate:
        return {"status": "error", "reason": "missing downloadUrl"}

    torrent_file = ""
    if effective_download and download_url:
        logger.info("Téléchargement .torrent via Prowlarr (score=%s)", best_score)
        torrent_file = download_torrent(best.get("title") or release_title, download_url)

    hash_check = None
    if effective_download and torrent_file and download_id:
        torrent_path = TORRENT_DIR / torrent_file
        info_hash = calculate_torrent_hash(str(torrent_path))
        hash_check = {
            "downloadId": download_id.upper(),
            "infoHash": info_hash.upper() if info_hash else None,
            "match": bool(info_hash and info_hash.upper() == download_id.upper())
        }
        logger.info(
            "Vérif hash: match=%s downloadId=%s infoHash=%s",
            hash_check["match"],
            download_id[:12] + "…" if download_id else "n/a",
            (info_hash[:12] + "…") if info_hash else "n/a"
        )
        if strict and not hash_check["match"]:
            try:
                torrent_path.unlink()
            except Exception:
                pass
            return {"status": "error", "reason": "hash mismatch", "hash_check": hash_check}

    grab_data = {
        "prowlarr_id": None,
        "download_id": download_id or None,
        "instance": instance_name or "unknown",
        "source": source or "webhook",
        "date": datetime.now(timezone.utc).isoformat(),
        "title": best.get("title") or release_title,
        "torrent_url": download_url or info_url or "",
        "tracker": best.get("indexer") or indexer_name,
        "indexer_id": best.get("indexerId")
    }

    success, message = insert_grab(grab_data, torrent_file or "")
    if not success:
        logger.error("Ingestion erreur insertion DB: %s", message)
        return {"status": "error", "reason": message}

    return {
        "status": "ok",
        "score": best_score,
        "downloadUrl": download_url,
        "hash_check": hash_check,
        "indexer": best.get("indexer") or indexer_name
    }


def handle_webhook_grab(
    payload: Dict[str, Any],
    prowlarr_url: str,
    prowlarr_api_key: str,
    min_score: int = 3,
    strict: bool = True,
    download: bool = True,
) -> Dict[str, Any]:
    event_type = payload.get("eventType")
    if event_type not in {"Grab", "Grabbed", "grab"}:
        logger.info("Webhook ignoré: eventType=%s", event_type)
        return {"status": "ignored", "reason": "eventType", "eventType": event_type}

    release = payload.get("release", {}) or {}
    release_title = release.get("releaseTitle") or release.get("title") or payload.get("title")
    if not release_title:
        logger.warning("Webhook invalide: releaseTitle manquant")
        return {"status": "error", "reason": "missing releaseTitle"}

    download_id = payload.get("downloadId") or ""
    indexer_name = release.get("indexer")
    release_size = release.get("size")
    instance_name = payload.get("instanceName") or payload.get("applicationUrl") or "unknown"

    logger.info(
        "Webhook reçu: instance=%s title=%s downloadId=%s",
        instance_name,
        release_title,
        download_id[:12] + "…" if download_id else "n/a"
    )

    # Alimente aussi le store historique consolide pour garder /grabs coherent
    # meme en cas d'evenements massifs webhook.
    try:
        upsert_grab_history([{
            "instance": instance_name,
            "raw_id": None,
            "event_type": "grabbed",
            "download_id": download_id or None,
            "source_title": release_title,
            "indexer": indexer_name,
            "size": release_size,
            "info_url": release.get("infoUrl"),
            "grabbed_at": datetime.now(timezone.utc).isoformat(),
        }])
    except Exception as exc:
        logger.warning("Webhook: impossible d'alimenter l'historique consolide: %s", exc)

    result = ingest_grab_event(
        instance_name=instance_name,
        source="webhook",
        release_title=release_title,
        download_id=download_id,
        indexer_name=indexer_name,
        release_size=release_size,
        info_url=release.get("infoUrl"),
        prowlarr_url=prowlarr_url,
        prowlarr_api_key=prowlarr_api_key,
        min_score=min_score,
        strict=strict,
        download=download,
        allow_download_for_history=False,
        allow_missing_candidate=False
    )
    if result.get("status") == "ok":
        logger.info("Webhook OK: grab enregistré title=%s", release_title)
    return result


def recover_from_history(
    record: Dict[str, Any],
    prowlarr_url: str,
    prowlarr_api_key: str,
    min_score: int = 3,
    strict: bool = True,
    download: bool = True,
) -> Dict[str, Any]:
    result = ingest_grab_event(
        instance_name=record.get("instance") or "history_reconcile",
        source="history_manual",
        release_title=record.get("source_title") or record.get("download_id") or "unknown",
        download_id=record.get("download_id") or "",
        indexer_name=record.get("indexer"),
        release_size=record.get("size"),
        info_url=record.get("info_url"),
        prowlarr_url=prowlarr_url,
        prowlarr_api_key=prowlarr_api_key,
        min_score=min_score,
        strict=strict,
        download=download,
        allow_download_for_history=True
    )
    if result.get("status") == "ok":
        result["indexer"] = record.get("indexer")
        result["fallback_used"] = False
        return result

    info_url = record.get("info_url")
    indexer_name = record.get("indexer")
    release_title = record.get("source_title") or record.get("download_id") or "unknown"
    download_id = record.get("download_id") or ""

    if not (info_url and indexer_name):
        result["indexer"] = record.get("indexer")
        result["fallback_used"] = False
        return result

    logger.info("Fallback recovery: tentative via indexer (%s)", indexer_name)
    try:
        recovery = _download_via_indexer(
            prowlarr_url=prowlarr_url,
            prowlarr_api_key=prowlarr_api_key,
            info_url=info_url,
            indexer_name=indexer_name,
            title=release_title
        )
    except Exception as exc:
        logger.warning("Fallback recovery erreur téléchargement: %s", exc)
        result["indexer"] = record.get("indexer")
        result["fallback_used"] = False
        return result

    if not recovery:
        result["indexer"] = record.get("indexer")
        result["fallback_used"] = False
        return result

    torrent_file = recovery.get("torrent_file")
    download_url = recovery.get("download_url")
    indexer_id = recovery.get("indexer_id")

    hash_check = None
    if download and torrent_file and download_id:
        torrent_path = TORRENT_DIR / torrent_file
        info_hash = calculate_torrent_hash(str(torrent_path))
        hash_check = {
            "downloadId": download_id.upper(),
            "infoHash": info_hash.upper() if info_hash else None,
            "match": bool(info_hash and info_hash.upper() == download_id.upper())
        }
        logger.info(
            "Fallback vérif hash: match=%s downloadId=%s infoHash=%s",
            hash_check["match"],
            download_id[:12] + "…" if download_id else "n/a",
            (info_hash[:12] + "…") if info_hash else "n/a"
        )
        if strict and not hash_check["match"]:
            try:
                torrent_path.unlink()
            except Exception:
                pass
            logger.warning("Fallback refusé: hash invalide (strict)")
            return {
                "status": "error",
                "reason": "hash mismatch",
                "hash_check": hash_check,
                "fallback_used": True,
                "indexer": record.get("indexer")
            }

    grab_data = {
        "prowlarr_id": None,
        "download_id": download_id or None,
        "instance": record.get("instance") or "history_reconcile",
        "source": "history_manual",
        "date": datetime.now(timezone.utc).isoformat(),
        "title": release_title,
        "torrent_url": download_url,
        "tracker": indexer_name,
        "indexer_id": indexer_id
    }
    success, message = insert_grab(grab_data, torrent_file or "")
    if not success:
        logger.error("Fallback erreur insertion DB: %s", message)
        return {"status": "error", "reason": message, "fallback_used": True, "indexer": record.get("indexer")}

    logger.info("Fallback OK: grab enregistré title=%s", release_title)
    return {
        "status": "ok",
        "score": None,
        "downloadUrl": download_url,
        "hash_check": hash_check,
        "fallback_used": True,
        "indexer": record.get("indexer")
    }
