from __future__ import annotations

from pathlib import Path
from paths import VERSION_FILE


_APP_VERSION: str | None = None


def get_app_version() -> str:
    """Retourne la version applicative depuis le fichier VERSION (source de vérité)."""
    global _APP_VERSION
    if _APP_VERSION is not None:
        return _APP_VERSION

    if not VERSION_FILE.exists():
        raise RuntimeError("Fichier VERSION introuvable. La version est obligatoire.")

    content = VERSION_FILE.read_text(encoding="utf-8").strip()
    if not content:
        raise RuntimeError("Fichier VERSION vide. La version est obligatoire.")

    _APP_VERSION = content
    return _APP_VERSION


APP_VERSION = get_app_version()
