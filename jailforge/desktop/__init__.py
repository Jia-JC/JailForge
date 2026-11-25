"""Desktop launcher backend for JailForge.

The desktop build serves a small, dependency-light local web UI from a bundled
HTTP server. It deliberately does not import Gradio, which keeps the EXE small
and avoids the fragile Gradio/PyInstaller integration.
"""

from .paths import APP_NAME, VERSION

__all__ = ["APP_NAME", "VERSION"]
