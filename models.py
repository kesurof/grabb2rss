# models.py
from pydantic import BaseModel
from typing import Optional

class GrabOut(BaseModel):
    id: int
    prowlarr_id: int
    grabbed_at: str
    title: str
    torrent_file: str
    tracker: Optional[str] = None

    class Config:
        from_attributes = True

class GrabStats(BaseModel):
    total_grabs: int
    latest_grab: Optional[str]
    oldest_grab: Optional[str]
    storage_size_mb: float
    tracker_stats: list
    top_torrents: list
    grabs_by_day: list

class SyncStatus(BaseModel):
    last_sync: Optional[str]
    last_error: Optional[str]
    is_running: bool
    next_sync: Optional[str]

class SyncLog(BaseModel):
    sync_at: str
    status: str
    error: Optional[str]
    grabs_count: int
    deduplicated_count: int
