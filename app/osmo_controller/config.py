"""
Persistance de la liste des caméras (cameras.json).

Format : [ { "name": "...", "address": "...", "model": "..." }, ... ]
"""

from __future__ import annotations
import json
from pathlib import Path


def load_cameras(path) -> list[dict]:
    p = Path(path)
    if not p.exists():
        return []
    return json.loads(p.read_text(encoding="utf-8"))


def save_cameras(path, cameras: list[dict]) -> None:
    Path(path).write_text(
        json.dumps(cameras, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
