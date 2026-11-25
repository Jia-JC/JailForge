"""Filesystem paths for source runs and the frozen (PyInstaller) EXE."""

from __future__ import annotations

import os
import sys
from pathlib import Path

APP_NAME = "JailForge"
VERSION = "0.1.0"


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def bundle_dir() -> Path:
    """Directory containing bundled data (``_MEIPASS`` in a one-file build)."""
    if is_frozen():
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
    return Path(__file__).resolve().parents[2]


def app_dir() -> Path:
    """Directory of the EXE (or the project root in a source checkout)."""
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def resource_path(relative: str | Path) -> Path:
    return bundle_dir() / relative


def _writable(path: Path) -> bool:
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".jf_write_test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        return True
    except OSError:
        return False


def results_dir() -> Path:
    """Prefer ``<exe>/results``; fall back to LocalAppData for read-only installs."""
    preferred = app_dir() / "results"
    if _writable(preferred):
        return preferred
    fallback = Path(os.getenv("LOCALAPPDATA", str(Path.home()))) / APP_NAME / "results"
    fallback.mkdir(parents=True, exist_ok=True)
    return fallback


def log_dir() -> Path:
    target = results_dir() / "logs"
    target.mkdir(parents=True, exist_ok=True)
    return target


def env_candidates() -> list[Path]:
    return [
        app_dir() / ".env",
        Path.cwd() / ".env",
        Path.home() / ".jailforge" / ".env",
        Path(os.getenv("LOCALAPPDATA", str(Path.home()))) / APP_NAME / ".env",
    ]


def load_env() -> Path | None:
    """Load the first existing ``.env`` without overriding real env vars."""
    try:
        from dotenv import load_dotenv
    except ImportError:  # pragma: no cover
        return None
    for candidate in env_candidates():
        if candidate.exists():
            load_dotenv(candidate, override=False)
            return candidate
    return None


def safe_run_name(prefix: str = "run") -> str:
    import time
    import uuid

    return f"{prefix}_{time.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:4]}"
