# settings_schema.py
from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator


class ProwlarrConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    url: str = ""
    api_key: str = ""
    history_page_size: int = 500


class RadarrConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    url: str = ""
    api_key: str = ""
    enabled: bool = True


class SonarrConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    url: str = ""
    api_key: str = ""
    enabled: bool = True


class SyncConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    interval: int = 3600
    retention_hours: int = 168
    dedup_hours: int = 168
    auto_purge: bool = True


class RssConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    domain: str = "localhost:8000"
    scheme: str = "http"
    title: str = "Grabb2RSS"
    description: str = "Prowlarr to RSS Feed"
    allowed_hosts: List[str] = Field(default_factory=list)

    @field_validator("scheme")
    @classmethod
    def validate_scheme(cls, value: str) -> str:
        value = value.lower().strip()
        if value not in {"http", "https"}:
            raise ValueError("doit être 'http' ou 'https'")
        return value


class CorsConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    allow_origins: List[str] = Field(default_factory=list)


class TorrentsConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expose_static: bool = False


class NetworkConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    retries: int = 3
    backoff_seconds: float = 1.0
    timeout_seconds: float = 10


class TorrentsDownloadConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    max_size_mb: int = 50


class LoggingConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    level: str = "INFO"

    @field_validator("level")
    @classmethod
    def validate_level(cls, value: str) -> str:
        value = value.upper().strip()
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if value not in allowed:
            raise ValueError(f"doit être un niveau de log valide ({', '.join(sorted(allowed))})")
        return value


class ApiKeyConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    key: str
    name: str
    enabled: bool = True
    created_at: Optional[str] = None


class AuthConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enabled: bool = False
    username: str = ""
    password_hash: str = ""
    api_keys: List[ApiKeyConfig] = Field(default_factory=list)
    cookie_secure: bool = False


class AppConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    host: str = "0.0.0.0"
    port: int = 8000


class SettingsConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    prowlarr: ProwlarrConfig = Field(default_factory=ProwlarrConfig)
    radarr: RadarrConfig = Field(default_factory=RadarrConfig)
    sonarr: SonarrConfig = Field(default_factory=SonarrConfig)
    sync: SyncConfig = Field(default_factory=SyncConfig)
    rss: RssConfig = Field(default_factory=RssConfig)
    app: AppConfig = Field(default_factory=AppConfig)
    cors: CorsConfig = Field(default_factory=CorsConfig)
    torrents: TorrentsConfig = Field(default_factory=TorrentsConfig)
    network: NetworkConfig = Field(default_factory=NetworkConfig)
    torrents_download: TorrentsDownloadConfig = Field(default_factory=TorrentsDownloadConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    auth: AuthConfig = Field(default_factory=AuthConfig)
    setup_completed: bool = False
