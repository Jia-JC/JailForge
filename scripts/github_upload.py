"""Upload the JailForge project and course report through the GitHub REST API.

Why not ``git push`` / ``gh``? On some campus networks ``github.com`` is blocked
while ``api.github.com`` is reachable. This script only needs HTTPS access to
``api.github.com`` and a personal access token, so it works in that environment.

Token resolution order:
1. ``--token-file`` (default: ``.secrets/github_token.txt``)
2. ``GITHUB_TOKEN`` environment variable

The token is never printed. Do not commit the token file.
"""

from __future__ import annotations

import argparse
import base64
import fnmatch
import os
import sys
from pathlib import Path
from typing import Any
from urllib.parse import quote

import requests

ROOT = Path(__file__).resolve().parents[1]
API = "https://api.github.com"
DEFAULT_TOKEN_FILE = ROOT / ".secrets" / "github_token.txt"
DEFAULT_OWNER = "Jia-JC"
DEFAULT_PROJECT = "JailForge"
DEFAULT_FORK = "LLM-Course-Assignments-2026"
DEFAULT_UPSTREAM_OWNER = "CAI-testbooks"
DEFAULT_UPSTREAM_REPO = "LLM-Course"
REPORT_PATH = "LLM-Course-Assignments-2026/07-Al-Safety/submissions/SX2616106-贾峻诚-07-AI-Safety.md"
REPORT_BRANCH = "submit/07-ai-safety-sx2616106"

EXCLUDE_DIRS = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    ".pytest_cache",
    ".testruns",
    ".tmp",
    ".secrets",
    ".idea",
    ".vscode",
    "node_modules",
    "build",
    "dist",
    "vendor",
}
EXCLUDE_SUFFIXES = {".pyc", ".pyo", ".log"}
EXCLUDE_NAMES = {".env", "install.log", "gradio_install.log", ".DS_Store", "Thumbs.db"}
EXCLUDE_GLOBS = [
    "results/**/trials.csv",
    "results/**/trials.jsonl",
    "results/**/cache.json",
    "results/real_smoke*",
]


class GitHubError(RuntimeError):
    def __init__(self, status: int, message: str) -> None:
        super().__init__(f"GitHub API {status}: {message}")
        self.status = status


class GitHubClient:
    def __init__(self, token: str) -> None:
        if not token:
            raise GitHubError(401, "empty token")
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "jailforge-uploader",
            }
        )

    # ------------------------------------------------------------------ #
    # Low level
    # ------------------------------------------------------------------ #
    def request(self, method: str, path: str, **kwargs: Any) -> requests.Response:
        url = path if path.startswith("http") else API + path
        response = self.session.request(method, url, timeout=60, **kwargs)
        if response.status_code >= 400:
            try:
                payload = response.json()
                message = payload.get("message", response.text[:300])
                errors = payload.get("errors")
                if errors:
                    message += f" | {errors}"
            except ValueError:
                message = response.text[:300]
            raise GitHubError(response.status_code, message)
        return response

    def get(self, path: str, **kwargs: Any) -> requests.Response:
        return self.request("GET", path, **kwargs)

    def post(self, path: str, **kwargs: Any) -> requests.Response:
        return self.request("POST", path, **kwargs)

    def patch(self, path: str, **kwargs: Any) -> requests.Response:
        return self.request("PATCH", path, **kwargs)

    def put(self, path: str, **kwargs: Any) -> requests.Response:
        return self.request("PUT", path, **kwargs)

    # ------------------------------------------------------------------ #
    # High level
    # ------------------------------------------------------------------ #
    def whoami(self) -> str:
        return self.get("/user").json()["login"]

    def repo_exists(self, owner: str, repo: str) -> bool:
        try:
            self.get(f"/repos/{owner}/{repo}")
            return True
        except GitHubError as exc:
            if exc.status == 404:
                return False
            raise

    def ensure_repo(self, owner: str, repo: str, description: str) -> tuple[str, bool]:
        login = self.whoami()
        if owner != login:
            raise GitHubError(
                403,
                f"token belongs to '{login}', but --owner is '{owner}'. "
                "Create the repo under the token owner, or use an org token.",
            )
        if self.repo_exists(owner, repo):
            return f"https://github.com/{owner}/{repo}", False
        self.post(
            "/user/repos",
            json={
                "name": repo,
                "description": description,
                "private": False,
                "auto_init": False,
                "has_issues": True,
                "has_wiki": False,
            },
        )
        return f"https://github.com/{owner}/{repo}", True

    def get_ref(self, owner: str, repo: str, branch: str) -> str | None:
        try:
            payload = self.get(f"/repos/{owner}/{repo}/git/ref/heads/{branch}").json()
            return payload["object"]["sha"]
        except GitHubError as exc:
            if exc.status in {404, 409}:
                return None
            raise

    def ensure_branch(self, owner: str, repo: str, branch: str, from_branch: str = "main") -> str:
        existing = self.get_ref(owner, repo, branch)
        if existing:
            return existing
        base_sha = self.get_ref(owner, repo, from_branch)
        if not base_sha:
            raise GitHubError(404, f"base branch '{from_branch}' not found in {owner}/{repo}")
        self.post(
            f"/repos/{owner}/{repo}/git/refs",
            json={"ref": f"refs/heads/{branch}", "sha": base_sha},
        )
        return base_sha

    def create_blob(self, owner: str, repo: str, content: bytes) -> str:
        encoded = base64.b64encode(content).decode("ascii")
        return self.post(
            f"/repos/{owner}/{repo}/git/blobs",
            json={"content": encoded, "encoding": "base64"},
        ).json()["sha"]

    def upload_tree(
        self,
        owner: str,
        repo: str,
        files: list[Path],
        message: str,
        branch: str = "main",
    ) -> str:
        head = self.get_ref(owner, repo, branch)
        if not head:
            # An empty repository has no Git database yet; GitHub rejects blob
            # creation with 409. Create the first commit through the Contents API.
            self.put(
                f"/repos/{owner}/{repo}/contents/README.md",
                json={
                    "message": "chore: initialize repository",
                    "content": base64.b64encode(b"# JailForge\n").decode("ascii"),
                    "branch": branch,
                },
            )
            head = self.get_ref(owner, repo, branch)
        base_tree = None
        parents: list[str] = []
        if head:
            parents = [head]
            base_tree = self.get(f"/repos/{owner}/{repo}/git/commits/{head}").json()["tree"]["sha"]

        entries = []
        for index, path in enumerate(files, start=1):
            relative = path.relative_to(ROOT).as_posix()
            blob_sha = self.create_blob(owner, repo, path.read_bytes())
            entries.append(
                {"path": relative, "mode": "100644", "type": "blob", "sha": blob_sha}
            )
            if index % 10 == 0 or index == len(files):
                print(f"  uploaded blobs {index}/{len(files)}")

        tree_payload: dict[str, Any] = {"tree": entries}
        if base_tree:
            tree_payload["base_tree"] = base_tree
        tree_sha = self.post(f"/repos/{owner}/{repo}/git/trees", json=tree_payload).json()["sha"]

        commit_payload: dict[str, Any] = {"message": message, "tree": tree_sha, "parents": parents}
        commit_sha = self.post(
            f"/repos/{owner}/{repo}/git/commits", json=commit_payload
        ).json()["sha"]

        if head:
            self.patch(
                f"/repos/{owner}/{repo}/git/refs/heads/{branch}",
                json={"sha": commit_sha, "force": False},
            )
        else:
            self.post(
                f"/repos/{owner}/{repo}/git/refs",
                json={"ref": f"refs/heads/{branch}", "sha": commit_sha},
            )
        return commit_sha

    def put_file(
        self,
        owner: str,
        repo: str,
        path: str,
        content: bytes,
        message: str,
        branch: str,
    ) -> str:
        encoded_path = quote(path, safe="/")
        sha = None
        try:
            existing = self.get(
                f"/repos/{owner}/{repo}/contents/{encoded_path}", params={"ref": branch}
            ).json()
            if isinstance(existing, dict):
                sha = existing.get("sha")
        except GitHubError as exc:
            if exc.status != 404:
                raise
        payload: dict[str, Any] = {
            "message": message,
            "content": base64.b64encode(content).decode("ascii"),
            "branch": branch,
        }
        if sha:
            payload["sha"] = sha
        result = self.put(
            f"/repos/{owner}/{repo}/contents/{encoded_path}", json=payload
        ).json()
        return result["content"]["html_url"]

    def create_pr(
        self,
        upstream_owner: str,
        upstream_repo: str,
        title: str,
        head: str,
        base: str,
        body: str,
    ) -> str:
        try:
            payload = self.post(
                f"/repos/{upstream_owner}/{upstream_repo}/pulls",
                json={"title": title, "head": head, "base": base, "body": body},
            ).json()
            return payload["html_url"]
        except GitHubError as exc:
            if exc.status != 422:
                raise
            owner, _, branch = head.partition(":")
            existing = self.get(
                f"/repos/{upstream_owner}/{upstream_repo}/pulls",
                params={"head": f"{owner}:{branch}", "state": "open"},
            ).json()
            if existing:
                return existing[0]["html_url"]
            raise


def collect_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(root)
        if any(part in EXCLUDE_DIRS for part in relative.parts):
            continue
        if path.suffix.lower() in EXCLUDE_SUFFIXES:
            continue
        if path.name in EXCLUDE_NAMES:
            continue
        relative_posix = relative.as_posix()
        if any(fnmatch.fnmatch(relative_posix, pattern) for pattern in EXCLUDE_GLOBS):
            continue
        try:
            if path.stat().st_size > 5 * 1024 * 1024:
                print(f"  skip large file: {relative_posix}")
                continue
        except OSError:
            continue
        files.append(path)
    return files


def read_token(path: Path | None) -> str:
    token = os.getenv("GITHUB_TOKEN", "").strip()
    if token:
        return token
    candidate = path or DEFAULT_TOKEN_FILE
    if candidate.exists():
        return candidate.read_text(encoding="utf-8").strip()
    raise SystemExit(
        f"GitHub token not found. Put a PAT with 'repo' scope in:\n  {candidate}\n"
        "or set the GITHUB_TOKEN environment variable."
    )


def cmd_project(args: argparse.Namespace) -> int:
    client = GitHubClient(read_token(args.token_file))
    url, created = client.ensure_repo(args.owner, args.repo, args.description)
    print(("created " if created else "exists  ") + url)
    files = collect_files(ROOT)
    print(f"uploading {len(files)} files to {args.owner}/{args.repo}:{args.branch}")
    if args.dry_run:
        for path in files:
            print("  " + path.relative_to(ROOT).as_posix())
        return 0
    commit = client.upload_tree(
        args.owner, args.repo, files, message=args.message, branch=args.branch
    )
    print(f"commit {commit[:12]} pushed to {url}/tree/{args.branch}")
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    client = GitHubClient(read_token(args.token_file))
    report_file = Path(args.report_file)
    if not report_file.is_absolute():
        report_file = ROOT / report_file
    if not report_file.exists():
        raise SystemExit(f"report not found: {report_file}")
    client.ensure_branch(args.owner, args.repo, args.branch, from_branch=args.base)
    url = client.put_file(
        args.owner,
        args.repo,
        args.path,
        report_file.read_bytes(),
        message=args.message,
        branch=args.branch,
    )
    print(f"report uploaded: {url}")
    return 0


def cmd_pr(args: argparse.Namespace) -> int:
    client = GitHubClient(read_token(args.token_file))
    body = Path(args.body_file).read_text(encoding="utf-8") if args.body_file else ""
    url = client.create_pr(
        args.upstream_owner,
        args.upstream_repo,
        title=args.title,
        head=f"{args.head_owner}:{args.head_branch}",
        base=args.base,
        body=body,
    )
    print(f"pull request: {url}")
    return 0


def cmd_all(args: argparse.Namespace) -> int:
    print("== 1/3 project repo ==")
    cmd_project(args)
    print("== 2/3 course report ==")
    args.branch = args.report_branch
    args.repo = args.report_repo
    cmd_report(args)
    print("== 3/3 pull request ==")
    cmd_pr(args)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    def add_common(p: argparse.ArgumentParser, branch_default: str = "main") -> None:
        p.add_argument("--token-file", type=Path, default=DEFAULT_TOKEN_FILE)
        p.add_argument("--owner", default=DEFAULT_OWNER)
        p.add_argument("--repo", default=DEFAULT_PROJECT)
        p.add_argument("--branch", default=branch_default)
        p.add_argument("--message", default="feat: JailForge v0.1 prototype")

    project = sub.add_parser("project", help="create repo and upload the project tree")
    add_common(project)
    project.add_argument("--description", default="JailForge: evolutionary jailbreak red-teaming and defense-in-depth evaluation")
    project.add_argument("--dry-run", action="store_true")
    project.set_defaults(func=cmd_project)

    report = sub.add_parser("report", help="upload the course report to the fork branch")
    add_common(report, REPORT_BRANCH)
    report.add_argument("--base", default="main")
    report.add_argument("--path", default=REPORT_PATH)
    report.add_argument("--report-file", default="docs/REPORT.md")
    report.set_defaults(func=cmd_report, repo=DEFAULT_FORK)

    pr = sub.add_parser("pr", help="open a pull request to the course upstream")
    pr.add_argument("--token-file", type=Path, default=DEFAULT_TOKEN_FILE)
    pr.add_argument("--upstream-owner", default=DEFAULT_UPSTREAM_OWNER)
    pr.add_argument("--upstream-repo", default=DEFAULT_UPSTREAM_REPO)
    pr.add_argument("--head-owner", default=DEFAULT_OWNER)
    pr.add_argument("--head-branch", default=REPORT_BRANCH)
    pr.add_argument("--base", default="main")
    pr.add_argument("--title", default="[作业07-Safety] SX2616106 贾峻诚 - LLM红队攻击与防御")
    pr.add_argument("--body-file", default="docs/PR_BODY.md")
    pr.set_defaults(func=cmd_pr)

    all_cmd = sub.add_parser("all", help="project + report + PR")
    all_cmd.add_argument("--token-file", type=Path, default=DEFAULT_TOKEN_FILE)
    all_cmd.add_argument("--owner", default=DEFAULT_OWNER)
    all_cmd.add_argument("--repo", default=DEFAULT_PROJECT)
    all_cmd.add_argument("--branch", default="main")
    all_cmd.add_argument("--report-branch", default=REPORT_BRANCH)
    all_cmd.add_argument("--report-repo", default=DEFAULT_FORK)
    all_cmd.add_argument("--description", default="JailForge: evolutionary jailbreak red-teaming and defense-in-depth evaluation")
    all_cmd.add_argument("--dry-run", action="store_true")
    all_cmd.add_argument("--base", default="main")
    all_cmd.add_argument("--path", default=REPORT_PATH)
    all_cmd.add_argument("--report-file", default="docs/REPORT.md")
    all_cmd.add_argument("--message", default="feat: JailForge v0.1 prototype")
    all_cmd.add_argument("--upstream-owner", default=DEFAULT_UPSTREAM_OWNER)
    all_cmd.add_argument("--upstream-repo", default=DEFAULT_UPSTREAM_REPO)
    all_cmd.add_argument("--head-owner", default=DEFAULT_OWNER)
    all_cmd.add_argument("--head-branch", default=REPORT_BRANCH)
    all_cmd.add_argument("--title", default="[作业07-Safety] SX2616106 贾峻诚 - LLM红队攻击与防御")
    all_cmd.add_argument("--body-file", default="docs/PR_BODY.md")
    all_cmd.set_defaults(func=cmd_all)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except GitHubError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
