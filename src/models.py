# models.py
from pydantic import BaseModel
from typing import Optional

class GrabOut(BaseModel):
    id: int
    prowlarr_id: Optional[int] = None
    download_id: Optional[str] = None
    instance: Optional[str] = None
    grabbed_at: str
    title: str
    torrent_file: str
    tracker: Optional[str] = None
    source_first_seen: Optional[str] = None
    source_last_seen: Optional[str] = None
    status: Optional[str] = None

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

# ==================== AUTH MODELS ====================

class LoginRequest(BaseModel):
    """Requête de connexion"""
    username: str
    password: str

class LoginResponse(BaseModel):
    """Réponse de connexion"""
    success: bool
    message: str
    session_token: Optional[str] = None

class AuthStatus(BaseModel):
    """Statut d'authentification"""
    authenticated: bool
    enabled: bool
    username: Optional[str] = None

class PasswordChangeRequest(BaseModel):
    """Requête de changement de mot de passe"""
    old_password: str
    new_password: str

class ApiKeyCreate(BaseModel):
    """Requête de création d'API key"""
    name: str
    enabled: bool = True

class ApiKeyResponse(BaseModel):
    """Réponse avec une API key"""
    key: str
    name: str
    enabled: bool
    created_at: str

class SetupAuthRequest(BaseModel):
    """Requête de configuration initiale de l'authentification"""
    username: str
    password: str
