"""JailForge desktop entry point.

Double-click the packaged EXE (or run ``python launcher.py``) to start a local
server and open the UI in the default browser. The server binds to 127.0.0.1
only and requires a per-session token for POST requests.
"""

from __future__ import annotations

import argparse
import json
import socket
import sys
import threading
import urllib.request
import webbrowser

from jailforge.desktop.paths import VERSION
from jailforge.desktop.server import create_server


def _show_error(message: str) -> None:
    try:
        import ctypes

        ctypes.windll.user32.MessageBoxW(0, message, "JailForge 启动失败", 0x10)
    except Exception:  # pragma: no cover
        pass


def _existing_instance(port: int) -> bool:
    if port <= 0:
        return False
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=1.2) as response:
            payload = json.loads(response.read().decode("utf-8"))
            return payload.get("app") == "JailForge"
    except Exception:
        return False


def _pick_port(preferred: int) -> int:
    if preferred <= 0:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(("127.0.0.1", 0))
            return int(sock.getsockname()[1])
    for port in range(preferred, preferred + 20):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="JailForge", description="JailForge desktop UI")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=17865)
    parser.add_argument("--no-browser", action="store_true", help="do not open a browser (for testing)")
    parser.add_argument("--token", default=None, help="fixed session token (for automated tests)")
    parser.add_argument("--version", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.version:
        print(VERSION)
        return 0
    if not args.no_browser and _existing_instance(args.port):
        webbrowser.open(f"http://127.0.0.1:{args.port}/")
        return 0

    port = _pick_port(args.port)
    server, service, _token = create_server(args.host, port, args.token)
    url = f"http://{args.host}:{port}/"
    if not args.no_browser:
        threading.Timer(0.7, lambda: webbrowser.open(url)).start()
    try:
        print(f"JailForge {VERSION} running at {url}")
        print(f"results directory: {service.results_dir}")
        print("Press Ctrl+C to stop (or use the 退出 button in the UI).")
    except Exception:
        pass
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001
        _show_error(f"{exc}\n\n请查看 results/logs/server_*.log 获取详细信息。")
        raise
