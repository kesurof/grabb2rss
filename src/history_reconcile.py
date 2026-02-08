from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from network import request_with_retries
from db import upsert_grab_history, get_config, set_config
from webhook_grab import ingest_grab_event

logger = logging.getLogger(__name__)


def _extract_records(data: Any) -> List[dict]:
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("records", "data", "results", "items"):
            value = data.get(key)
            if isinstance(value, list):
                return value
    return []


def _build_payload(record: dict, instance: str) -> dict:
    data = record.get("data") or {}
    return {
        "instance": instance,
        "raw_id": record.get("id"),
        "event_type": record.get("eventType"),
        "download_id": record.get("downloadId"),
        "source_title": record.get("sourceTitle") or data.get("title") or data.get("releaseTitle"),
        "indexer": record.get("indexer") or data.get("indexer"),
        "size": record.get("size") or data.get("size"),
        "info_url": record.get("infoUrl") or data.get("infoUrl") or data.get("downloadUrl"),
        "grabbed_at": record.get("date") or record.get("grabbedAt"),
    }


def _parse_iso_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        normalized = value.replace("Z", "+00:00")
        dt = datetime.fromisoformat(normalized)
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def _cursor_key(instance: str) -> str:
    return f"HISTORY_CURSOR::{instance.lower()}"


def _load_cursor(instance: str) -> dict:
    raw = get_config(_cursor_key(instance))
    if not raw:
        return {"grabbed_at": None, "raw_id": None}
    try:
        grabbed_at, raw_id = raw.split("|", 1)
        return {"grabbed_at": grabbed_at or None, "raw_id": int(raw_id) if raw_id else None}
    except Exception:
        return {"grabbed_at": None, "raw_id": None}


def _save_cursor(instance: str, grabbed_at: str | None, raw_id: int | None) -> None:
    if not grabbed_at:
        return
    value = f"{grabbed_at}|{raw_id if raw_id is not None else ''}"
    set_config(_cursor_key(instance), value, "Cursor de reconciliation historique")


def _is_newer_than_cursor(record: dict, cursor: dict) -> bool:
    cursor_dt = _parse_iso_datetime(cursor.get("grabbed_at"))
    if cursor_dt is None:
        return True
    rec_dt = _parse_iso_datetime(record.get("date") or record.get("grabbedAt"))
    if rec_dt is None:
        return False
    if rec_dt > cursor_dt:
        return True
    if rec_dt < cursor_dt:
        return False
    cursor_raw = cursor.get("raw_id")
    rec_raw = record.get("id")
    if cursor_raw is None or rec_raw is None:
        return False
    try:
        return int(rec_raw) > int(cursor_raw)
    except Exception:
        return False


def sync_grab_history(
    history_apps: List[dict],
    event_type: str = "grabbed",
    page_size: int = 200,
    max_pages: int = 10,
    lookback_days: int = 7,
    full_scan: bool = False,
    download_from_history: bool = True,
    min_score: int = 3,
    strict_hash: bool = False,
    ingestion_mode: str = "webhook_plus_history",
) -> Dict[str, Any]:
    """Recupere l'historique Radarr/Sonarr et alimente le store consolide."""
    if not history_apps:
        return {"status": "skipped", "reason": "no_apps"}
    if ingestion_mode == "webhook_only":
        return {"status": "skipped", "reason": "ingestion_mode_webhook_only"}

    from config import PROWLARR_URL, PROWLARR_API_KEY

    summary: Dict[str, Any] = {"apps": [], "inserted": 0, "ingested": 0}
    lookback_start = datetime.now(timezone.utc) - timedelta(days=max(1, lookback_days))

    for app in history_apps:
        if not isinstance(app, dict):
            continue
        if not app.get("enabled", True):
            continue
        if not app.get("name") or not app.get("url") or not app.get("api_key"):
            continue

        base = str(app["url"]).rstrip("/")
        instance = str(app["name"]).strip()
        headers = {"X-Api-Key": app["api_key"]}

        total = 0
        grabbed = 0
        ingested = 0
        inserted = 0
        filtered_old = 0
        seen_download_ids: set[str] = set()
        cursor = _load_cursor(instance)
        highest_dt = _parse_iso_datetime(cursor.get("grabbed_at"))
        highest_dt_raw = cursor.get("grabbed_at")
        highest_raw_id = cursor.get("raw_id")
        stop_pagination = False

        for page in range(1, max_pages + 1):
            url = f"{base}/api/v3/history"
            params = {
                "page": page,
                "pageSize": page_size,
                "sortKey": "date",
                "sortDirection": "descending",
            }
            try:
                response = request_with_retries("GET", url, headers=headers, params=params)
            except Exception as exc:
                logger.warning("Historique consolide: erreur %s (%s): %s", instance, url, exc)
                break

            records = _extract_records(response.json())
            total += len(records)
            if not records:
                break

            page_payloads: List[dict] = []
            for record in records:
                if event_type and record.get("eventType") != event_type:
                    continue
                rec_dt = _parse_iso_datetime(record.get("date") or record.get("grabbedAt"))
                if rec_dt and rec_dt < lookback_start:
                    filtered_old += 1
                    stop_pagination = True
                    continue
                if not full_scan and not _is_newer_than_cursor(record, cursor):
                    continue
                grabbed += 1
                payload = _build_payload(record, instance)
                page_payloads.append(payload)

                payload_download_id = (payload.get("download_id") or "").strip()
                if payload_download_id:
                    if payload_download_id in seen_download_ids:
                        continue
                    seen_download_ids.add(payload_download_id)
                else:
                    continue

                try:
                    ingest_result = ingest_grab_event(
                        instance_name=instance,
                        source="history_sync",
                        release_title=payload.get("source_title") or payload.get("download_id") or "unknown",
                        download_id=payload_download_id,
                        indexer_name=payload.get("indexer"),
                        release_size=payload.get("size"),
                        info_url=payload.get("info_url"),
                        prowlarr_url=PROWLARR_URL,
                        prowlarr_api_key=PROWLARR_API_KEY,
                        min_score=min_score,
                        strict=strict_hash,
                        download=download_from_history,
                        allow_download_for_history=download_from_history,
                        allow_missing_candidate=True,
                    )
                    if ingest_result.get("status") == "ok":
                        ingested += 1
                except Exception as exc:
                    logger.warning("Ingestion historique echouee (%s): %s", instance, exc)
                rec_raw_id = record.get("id")
                if rec_dt and (highest_dt is None or rec_dt > highest_dt):
                    highest_dt = rec_dt
                    highest_dt_raw = record.get("date") or record.get("grabbedAt")
                    try:
                        highest_raw_id = int(rec_raw_id) if rec_raw_id is not None else None
                    except Exception:
                        highest_raw_id = None
                elif rec_dt and highest_dt and rec_dt == highest_dt:
                    try:
                        rec_raw_id_int = int(rec_raw_id) if rec_raw_id is not None else None
                    except Exception:
                        rec_raw_id_int = None
                    if rec_raw_id_int is not None and (highest_raw_id is None or rec_raw_id_int > highest_raw_id):
                        highest_raw_id = rec_raw_id_int

            page_result = upsert_grab_history(page_payloads)
            inserted += page_result.get("inserted", 0)

            if len(records) < page_size:
                break
            if stop_pagination:
                break

        _save_cursor(instance, highest_dt_raw, highest_raw_id)
        summary["inserted"] += inserted
        summary["ingested"] += ingested
        summary["apps"].append({
            "instance": instance,
            "records_total": total,
            "records_grabbed": grabbed,
            "records_filtered_old": filtered_old,
            "inserted": inserted,
            "ingested": ingested,
            "full_scan": full_scan,
            "download_from_history": download_from_history,
            "min_score": min_score,
            "strict_hash": strict_hash,
            "ingestion_mode": ingestion_mode,
            "cursor": _load_cursor(instance),
        })

    return summary
