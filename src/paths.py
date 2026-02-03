from __future__ import annotations

from pathlib import Path
import os

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"
WEB_DIR = PROJECT_ROOT / "web"
TEMPLATES_DIR = WEB_DIR / "templates"
STATIC_DIR = WEB_DIR / "static"
VERSION_FILE = PROJECT_ROOT / "VERSION"
CONFIG_DIR = Path(os.getenv("CONFIG_DIR", "/config"))
SETTINGS_FILE = CONFIG_DIR / "settings.yml"
DATA_DIR = Path(os.getenv("DATA_DIR", "/app/data"))
TORRENT_DIR = DATA_DIR / "torrents"
