"""Create the GitHub release and upload the Windows assets.

Token resolution: ``.secrets/github_token.txt`` or ``GITHUB_TOKEN``.
Uploads use ``https://uploads.github.com``; if that host is blocked on your
network, use the GitHub web UI to attach the files manually.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import sys
from pathlib import Path

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
    def __init__(self, token: str, owner: str, repo: str) -> None:
        self.token = token
        self.owner = owner
        self.repo = repo
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "jailforge-release",
            }
        )

    def _check(self, response: requests.Response) -> requests.Response:
        if response.status_code >= 400:
            try:
                message = response.json().get("message", response.text[:300])
            except ValueError:
                message = response.text[:300]
            raise RuntimeError(f"GitHub API {response.status_code}: {message}")
        return response

    def get_release(self, tag: str) -> dict | None:
        response = self.session.get(f"{API}/repos/{self.owner}/{self.repo}/releases/tags/{tag}", timeout=60)
        if response.status_code == 404:
            return None
        return self._check(response).json()

    def create_or_update_release(self, tag: str, name: str, body: str) -> dict:
        existing = self.get_release(tag)
        if existing:
            response = self.session.patch(
                f"{API}/repos/{self.owner}/{self.repo}/releases/{existing['id']}",
                json={"name": name, "body": body, "prerelease": False, "draft": False},
                timeout=60,
            )
            return self._check(response).json()
        response = self.session.post(
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
            timeout=60,
        )
        return self._check(response).json()

    def list_assets(self, release_id: int) -> list[dict]:
        response = self.session.get(
            f"{API}/repos/{self.owner}/{self.repo}/releases/{release_id}/assets",
            timeout=60,
        )
        return self._check(response).json()

    def delete_asset(self, asset_id: int) -> None:
        response = self.session.delete(
            f"{API}/repos/{self.owner}/{self.repo}/releases/assets/{asset_id}",
            timeout=60,
        )
        if response.status_code not in {204, 404}:
            self._check(response)

    def upload_asset(self, release_id: int, path: Path) -> dict:
        for asset in self.list_assets(release_id):
            if asset["name"] == path.name:
                self.delete_asset(asset["id"])
        with path.open("rb") as handle:
            response = self.session.post(
                f"{UPLOAD}/repos/{self.owner}/{self.repo}/releases/{release_id}/assets",
                params={"name": path.name},
                data=handle,
                headers={"Content-Type": "application/octet-stream"},
                timeout=600,
            )
        return self._check(response).json()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--owner", default="Jia-JC")
    parser.add_argument("--repo", default="JailForge")
    parser.add_argument("--tag", default="v0.1.0")
    parser.add_argument("--token-file", type=Path, default=TOKEN_FILE)
    parser.add_argument("--release-dir", type=Path, default=ROOT / "release")
    parser.add_argument("--notes", type=Path, default=ROOT / "docs" / "RELEASE_NOTES_v0.1.0.md")
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

    client = ReleaseClient(read_token(args.token_file), args.owner, args.repo)
    release = client.create_or_update_release(args.tag, f"JailForge {args.tag} — Windows 桌面版", body)
    print(f"release: {release['html_url']}")
    for asset in assets:
        uploaded = client.upload_asset(release["id"], asset)
        print(f"asset: {uploaded['name']} -> {uploaded['browser_download_url']}")
    print("done")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
