"""Persistent response cache so repeated evaluations are cheap and reproducible."""

from __future__ import annotations

import json
from pathlib import Path


class ResponseCache:
    def __init__(self, path: str | Path, enabled: bool = True) -> None:
        self.path = Path(path)
        self.enabled = enabled
        self.data: dict[str, str] = {}
        if self.enabled and self.path.exists():
            try:
                loaded = json.loads(self.path.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    self.data = {str(k): str(v) for k, v in loaded.items()}
            except (ValueError, OSError):
                self.data = {}

    def get(self, key: str) -> str | None:
        return self.data.get(key) if self.enabled else None

    def set(self, key: str, value: str) -> None:
        if self.enabled:
            self.data[key] = value

    def save(self) -> None:
        if not self.enabled:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(self.data, ensure_ascii=False),
            encoding="utf-8",
        )
