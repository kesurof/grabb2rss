#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VERSION_PATH = ROOT / "VERSION"
README_PATH = ROOT / "README.md"

MARKER_START = "<!-- version:start -->"
MARKER_END = "<!-- version:end -->"


def main() -> int:
    version = VERSION_PATH.read_text(encoding="utf-8").strip()
    readme = README_PATH.read_text(encoding="utf-8")

    if MARKER_START not in readme or MARKER_END not in readme:
        raise SystemExit("Markers not found in README.md")

    before, rest = readme.split(MARKER_START, 1)
    _, after = rest.split(MARKER_END, 1)
    updated = f"{before}{MARKER_START}v{version}{MARKER_END}{after}"

    if updated != readme:
        README_PATH.write_text(updated, encoding="utf-8")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
