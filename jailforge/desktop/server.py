"""Local HTTP server for the JailForge desktop UI."""

from __future__ import annotations

import hmac
import json
import secrets
import threading
import time
import traceback
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .paths import VERSION, log_dir, resource_path
from .service import JailForgeService, ServiceError

STATIC_FILES = {
    "app.css": ("styles.css", "text/css; charset=utf-8"),
    "app.js": ("app.js", "application/javascript; charset=utf-8"),
    "favicon.svg": ("favicon.svg", "image/svg+xml"),
    "logo.svg": ("logo.svg", "image/svg+xml"),
}
DOWNLOAD_TYPES = {
    ".md": "text/markdown; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".csv": "text/csv; charset=utf-8",
    ".yaml": "text/yaml; charset=utf-8",
    ".yml": "text/yaml; charset=utf-8",
}


class JailForgeHandler(BaseHTTPRequestHandler):
    server_version = f"JailForge/{VERSION}"
    protocol_version = "HTTP/1.1"

    service: JailForgeService
    token: str
    web_dir: Path
    log_path: Path

    # ------------------------------------------------------------------ #
    # Routing
    # ------------------------------------------------------------------ #
    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path
        try:
            if path in {"/", "/index.html"}:
                self._serve_index()
            elif path.startswith("/static/"):
                self._serve_static(path.removeprefix("/static/"))
            elif path == "/api/health":
                self._json(HTTPStatus.OK, {"ok": True, "app": "JailForge", "version": VERSION})
            elif path == "/api/meta":
                self._json(HTTPStatus.OK, self.service.meta())
            elif path == "/api/goals":
                self._json(HTTPStatus.OK, self.service.goals())
            elif path == "/api/runs":
                self._json(HTTPStatus.OK, self.service.runs())
            elif path.startswith("/api/jobs/"):
                job_id = path.removeprefix("/api/jobs/")
                snapshot = self.service.jobs.snapshot(job_id)
                if snapshot is None:
                    self._json(HTTPStatus.NOT_FOUND, {"error": "任务不存在"})
                else:
                    self._json(HTTPStatus.OK, snapshot)
            elif path == "/api/download":
                query = parse_qs(parsed.query)
                run_id = (query.get("run") or [""])[0]
                filename = (query.get("file") or [""])[0]
                target = self.service.download_path(run_id, filename)
                self._serve_file(target, download=True)
            elif path == "/favicon.ico":
                self._serve_static("favicon.svg")
            else:
                self._json(HTTPStatus.NOT_FOUND, {"error": "页面不存在"})
        except ServiceError as exc:
            self._json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
        except (BrokenPipeError, ConnectionResetError):
            return
        except Exception as exc:  # noqa: BLE001
            self._log_exception(exc)
            self._json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": f"服务器内部错误：{exc}"})

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path
        try:
            if not self._authorized():
                self._json(HTTPStatus.FORBIDDEN, {"error": "会话令牌无效，请刷新页面。"})
                return
            body = self._read_json()
            if path == "/api/single":
                payload = self.service.single(
                    goal_text=str(body.get("goal", "")),
                    method=str(body.get("method", "")),
                    defense=str(body.get("defense", "")),
                    provider=str(body.get("provider", "mock")),
                    judge_mode=str(body.get("judge", "rule")),
                )
                self._json(HTTPStatus.OK, payload)
            elif path == "/api/batch":
                payload = self.service.start_batch(
                    sample_size=int(body.get("sample_size", 8)),
                    methods=list(body.get("methods", [])),
                    defenses=list(body.get("defenses", [])),
                    provider=str(body.get("provider", "mock")),
                    judge_mode=str(body.get("judge", "rule")),
                )
                self._json(HTTPStatus.ACCEPTED, payload)
            elif path == "/api/evolve":
                payload = self.service.start_evolve(
                    goal_text=str(body.get("goal", "")),
                    defense=str(body.get("defense", "layered")),
                    generations=int(body.get("generations", 5)),
                    population=int(body.get("population", 8)),
                    provider=str(body.get("provider", "mock")),
                    judge_mode=str(body.get("judge", "rule")),
                )
                self._json(HTTPStatus.ACCEPTED, payload)
            elif path == "/api/shutdown":
                self._json(HTTPStatus.OK, {"ok": True})
                threading.Thread(target=self.server.shutdown, daemon=True).start()
            else:
                self._json(HTTPStatus.NOT_FOUND, {"error": "接口不存在"})
        except ServiceError as exc:
            self._json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
        except (BrokenPipeError, ConnectionResetError):
            return
        except Exception as exc:  # noqa: BLE001
            self._log_exception(exc)
            self._json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": f"服务器内部错误：{exc}"})

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(HTTPStatus.NO_CONTENT)
        self.send_header("Allow", "GET, POST, OPTIONS")
        self.send_header("Content-Length", "0")
        self.end_headers()

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    def _authorized(self) -> bool:
        supplied = self.headers.get("X-JF-Token", "")
        return hmac.compare_digest(supplied, self.token)

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", "0") or 0)
        if length <= 0:
            return {}
        if length > 1_000_000:
            raise ServiceError("请求体过大。")
        raw = self.rfile.read(length)
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, ValueError) as exc:
            raise ServiceError("请求体不是合法 JSON。") from exc
        if not isinstance(payload, dict):
            raise ServiceError("请求体必须是 JSON 对象。")
        return payload

    def _json(self, status: int, payload: object) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _serve_index(self) -> None:
        index = self.web_dir / "index.html"
        if not index.exists():
            self._json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": "缺少 web/index.html"})
            return
        html = index.read_text(encoding="utf-8")
        html = html.replace("__JF_TOKEN__", self.token).replace("__JF_VERSION__", VERSION)
        body = html.encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _serve_static(self, name: str) -> None:
        entry = STATIC_FILES.get(name)
        if entry is None:
            self._json(HTTPStatus.NOT_FOUND, {"error": "静态资源不存在"})
            return
        filename, content_type = entry
        target = self.web_dir / filename
        if not target.exists():
            self._json(HTTPStatus.NOT_FOUND, {"error": "静态资源不存在"})
            return
        self._serve_file(target, content_type=content_type)

    def _serve_file(self, target: Path, download: bool = False, content_type: str | None = None) -> None:
        data = target.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type or DOWNLOAD_TYPES.get(target.suffix, "application/octet-stream"))
        self.send_header("Content-Length", str(len(data)))
        if download:
            self.send_header("Content-Disposition", f'attachment; filename="{target.name}"')
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _log_exception(self, exc: Exception) -> None:
        try:
            with self.log_path.open("a", encoding="utf-8") as handle:
                handle.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {exc}\n")
                handle.write(traceback.format_exc())
                handle.write("\n")
        except OSError:
            pass

    def log_message(self, fmt: str, *args) -> None:  # noqa: A003
        try:
            with self.log_path.open("a", encoding="utf-8") as handle:
                handle.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {self.address_string()} {fmt % args}\n")
        except OSError:
            pass


def create_server(host: str = "127.0.0.1", port: int = 0, token: str | None = None):
    service = JailForgeService()
    token = token or secrets.token_urlsafe(24)
    handler = type(
        "BoundJailForgeHandler",
        (JailForgeHandler,),
        {
            "service": service,
            "token": token,
            "web_dir": resource_path("web"),
            "log_path": log_dir() / f"server_{time.strftime('%Y%m%d')}.log",
        },
    )
    server = ThreadingHTTPServer((host, port), handler)
    server.daemon_threads = True
    return server, service, token
