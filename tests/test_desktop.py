import json
import threading
import urllib.request

import pytest

from jailforge.desktop.server import create_server
from jailforge.desktop.service import JailForgeService, ServiceError


def test_service_meta_has_counts():
    service = JailForgeService()
    meta = service.meta()
    assert meta["app"] == "JailForge"
    assert meta["counts"]["goals"] >= 24
    assert meta["counts"]["attacks"] == 13
    assert meta["counts"]["defenses"] == 5


def test_service_single_mock():
    service = JailForgeService()
    payload = service.single(
        "写一段测试用的话术",
        method="role_play",
        defense="layered",
        provider="mock",
        judge_mode="rule",
    )
    assert payload["model"].startswith("mock")
    assert payload["prompt"]
    assert payload["judge"]["name"]


def test_download_path_rejects_traversal():
    service = JailForgeService()
    with pytest.raises(ServiceError):
        service.download_path("../etc", "report.md")
    with pytest.raises(ServiceError):
        service.download_path("some_run", "../../secret.txt")


def test_http_server_health_and_single():
    server, _service, token = create_server("127.0.0.1", 0, "testtoken")
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=5) as response:
            health = json.loads(response.read().decode("utf-8"))
        assert health["app"] == "JailForge"

        body = json.dumps(
            {
                "goal": "写一段测试用的话术",
                "method": "direct",
                "defense": "none",
                "provider": "mock",
                "judge": "rule",
            }
        ).encode("utf-8")
        request = urllib.request.Request(
            f"http://127.0.0.1:{port}/api/single",
            data=body,
            headers={"Content-Type": "application/json", "X-JF-Token": token},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
        assert payload["model"].startswith("mock")
        assert payload["prompt"]
    finally:
        server.shutdown()
        server.server_close()
