from __future__ import annotations

from pathlib import Path


_APP_VERSION: str | None = None


def get_app_version() -> str:
    """Retourne la version applicative depuis le fichier VERSION (source de vérité)."""
    global _APP_VERSION
    if _APP_VERSION is not None:
        return _APP_VERSION

    version_file = Path(__file__).resolve().parent / "VERSION"
    if not version_file.exists():
        raise RuntimeError("Fichier VERSION introuvable. La version est obligatoire.")

    content = version_file.read_text(encoding="utf-8").strip()
    if not content:
        raise RuntimeError("Fichier VERSION vide. La version est obligatoire.")

    _APP_VERSION = content
    return _APP_VERSION


APP_VERSION = get_app_version()
