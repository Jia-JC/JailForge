"""Create the GitHub release and upload the Windows assets.

Token resolution: ``.secrets/github_token.txt`` or ``GITHUB_TOKEN``.
Uploads use ``https://uploads.github.com``; if that host is blocked on your
network, use the GitHub web UI to attach the files manually.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import quote

import requests

ROOT = Path(__file__).resolve().parents[1]
API = "https://api.github.com"
UPLOAD = "https://uploads.github.com"
TOKEN_FILE = ROOT / ".secrets" / "github_token.txt"


def read_token(path: Path | None = None) -> str:
    token = os.getenv("GITHUB_TOKEN", "").strip()
    if token:
        return token
    candidate = path or TOKEN_FILE
    if not candidate.exists():
        raise SystemExit(
            f"GitHub token not found: {candidate}\n"
            "Put a classic PAT with 'repo' scope there, or set GITHUB_TOKEN."
        )
    return candidate.read_text(encoding="utf-8").strip()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class ReleaseClient:
    def __init__(self, token: str, owner: str, repo: str, upload_ip: str | None = None) -> None:
        self.token = token
        self.owner = owner
        self.repo = repo
        self.upload_ip = upload_ip
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "jailforge-release",
            }
        )

    def _request(self, method: str, url: str, **kwargs: object) -> requests.Response:
        last_error: Exception | None = None
        timeout = kwargs.pop("timeout", 60)
        for attempt in range(4):
            try:
                return self.session.request(method, url, timeout=timeout, **kwargs)
            except requests.RequestException as exc:
                last_error = exc
                time.sleep(1.5 * (attempt + 1))
        raise RuntimeError(f"request failed after retries: {last_error}")

    def _check(self, response: requests.Response) -> requests.Response:
        if response.status_code >= 400:
            try:
                message = response.json().get("message", response.text[:300])
            except ValueError:
                message = response.text[:300]
            raise RuntimeError(f"GitHub API {response.status_code}: {message}")
        return response

    def get_release(self, tag: str) -> dict | None:
        response = self._request("GET", f"{API}/repos/{self.owner}/{self.repo}/releases/tags/{tag}")
        if response.status_code == 404:
            return None
        return self._check(response).json()

    def create_or_update_release(self, tag: str, name: str, body: str) -> dict:
        existing = self.get_release(tag)
        if existing:
            response = self._request(
                "PATCH",
                f"{API}/repos/{self.owner}/{self.repo}/releases/{existing['id']}",
                json={"name": name, "body": body, "prerelease": False, "draft": False},
            )
            return self._check(response).json()
        response = self._request(
            "POST",
            f"{API}/repos/{self.owner}/{self.repo}/releases",
            json={
                "tag_name": tag,
                "target_commitish": "main",
                "name": name,
                "body": body,
                "draft": False,
                "prerelease": False,
                "make_latest": "true",
            },
        )
        return self._check(response).json()

    def list_assets(self, release_id: int) -> list[dict]:
        response = self._request(
            "GET", f"{API}/repos/{self.owner}/{self.repo}/releases/{release_id}/assets"
        )
        return self._check(response).json()

    def delete_asset(self, asset_id: int) -> None:
        response = self._request(
            "DELETE", f"{API}/repos/{self.owner}/{self.repo}/releases/assets/{asset_id}"
        )
        if response.status_code not in {204, 404}:
            self._check(response)

    def upload_asset(self, release_id: int, path: Path) -> dict:
        for asset in self.list_assets(release_id):
            if asset["name"] == path.name:
                self.delete_asset(asset["id"])
        if self.upload_ip:
            return self._upload_with_curl(release_id, path, self.upload_ip)
        with path.open("rb") as handle:
            response = self._request(
                "POST",
                f"{UPLOAD}/repos/{self.owner}/{self.repo}/releases/{release_id}/assets",
                params={"name": path.name},
                data=handle,
                headers={"Content-Type": "application/octet-stream"},
                timeout=600,
            )
        return self._check(response).json()

    def _upload_with_curl(self, release_id: int, path: Path, ip: str) -> dict:
        url = (
            f"{UPLOAD}/repos/{self.owner}/{self.repo}/releases/{release_id}/assets"
            f"?name={quote(path.name)}"
        )
        command = [
            "curl.exe",
            "-sS",
            "--fail-with-body",
            "--max-time",
            "600",
            "--resolve",
            f"uploads.github.com:443:{ip}",
            "-X",
            "POST",
            url,
            "-H",
            f"Authorization: Bearer {self.token}",
            "-H",
            "Content-Type: application/octet-stream",
            "--data-binary",
            f"@{path}",
        ]
        result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace")
        if result.returncode != 0:
            raise RuntimeError(
                f"curl upload failed (exit {result.returncode}): {result.stderr[-500:] or result.stdout[-500:]}"
            )
        try:
            return json.loads(result.stdout)
        except ValueError as exc:
            raise RuntimeError(f"unexpected upload response: {result.stdout[:300]}") from exc


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--owner", default="Jia-JC")
    parser.add_argument("--repo", default="JailForge")
    parser.add_argument("--tag", default="v0.1.0")
    parser.add_argument("--token-file", type=Path, default=TOKEN_FILE)
    parser.add_argument("--release-dir", type=Path, default=ROOT / "release")
    parser.add_argument("--notes", type=Path, default=ROOT / "docs" / "RELEASE_NOTES_v0.1.0.md")
    parser.add_argument("--skip-upload", action="store_true", help="only create/update the release metadata")
    parser.add_argument("--upload-ip", default=None, help="use curl --resolve to this GitHub uploads IP")
    args = parser.parse_args()

    release_dir = args.release_dir
    assets = [
        release_dir / "JailForge.exe",
        release_dir / "JailForge-portable-win64.zip",
        release_dir / "SHA256SUMS.txt",
    ]
    for asset in assets:
        if not asset.exists():
            raise SystemExit(f"missing asset: {asset}")

    body = args.notes.read_text(encoding="utf-8")
    body += "\n\n## SHA256\n\n```text\n"
    body += "\n".join(f"{sha256(path)}  {path.name}" for path in assets[:2])
    body += "\n```\n"

    client = ReleaseClient(read_token(args.token_file), args.owner, args.repo, upload_ip=args.upload_ip)
    release = client.create_or_update_release(args.tag, f"JailForge {args.tag} — Windows 桌面版", body)
    print(f"release: {release['html_url']}")
    print(f"release_id: {release['id']}")
    if args.skip_upload:
        print("upload skipped")
        return 0
    # Upload the checksum first: it is tiny and validates the upload path quickly.
    assets = [assets[2], assets[0], assets[1]]
    try:
        for asset in assets:
            uploaded = client.upload_asset(release["id"], asset)
            print(f"asset: {uploaded['name']} -> {uploaded['browser_download_url']}")
    except Exception as exc:  # noqa: BLE001
        print(f"UPLOAD_FAILED: {exc}", file=sys.stderr)
        print(f"release created without all assets: {release['html_url']}")
        print("请在这个 Release 页面点击 Edit → 拖入 release/ 下的 JailForge.exe 与 JailForge-portable-win64.zip")
        return 1
    print("done")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
