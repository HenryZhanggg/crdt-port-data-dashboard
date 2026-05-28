from __future__ import annotations

import argparse
import base64
import json
import os
from pathlib import Path
from typing import Any

import requests


BASE_DIR = Path(__file__).resolve().parents[1]
DEFAULT_REPO = "crdt-port-data-dashboard"
API_ROOT = "https://api.github.com"

FILES_TO_UPLOAD = [
    ".gitignore",
    ".streamlit/config.toml",
    "README.md",
    "requirements.txt",
    "requirements-dev.txt",
    "app.py",
    "api_connectors.py",
    "data/assets.csv",
    "data/data_sources.csv",
    "data/high_score_dataset_catalog.csv",
    "data/high_score_dataset_catalog.json",
    "data/partners.csv",
    "data/service_area.geojson",
    "data/transport_events.csv",
    "data/weather_observations.csv",
    "scripts/extract_docx_high_score_sources.py",
    "scripts/ingest_open_raw_data.py",
    "scripts/publish_to_github_api.py",
]


def github_request(
    session: requests.Session,
    method: str,
    url: str,
    *,
    expected: set[int],
    **kwargs: Any,
) -> requests.Response:
    response = session.request(method, url, timeout=60, **kwargs)
    if response.status_code not in expected:
        detail = response.text[:1200]
        raise RuntimeError(f"GitHub API {method} {url} failed with {response.status_code}: {detail}")
    return response


def make_session(token: str) -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "CRDT-Port dashboard publisher",
        }
    )
    return session


def ensure_repo(session: requests.Session, owner: str, repo: str, private: bool) -> None:
    repo_url = f"{API_ROOT}/repos/{owner}/{repo}"
    response = session.get(repo_url, timeout=30)
    if response.status_code == 200:
        print(f"Repository already exists: https://github.com/{owner}/{repo}")
        return
    if response.status_code != 404:
        raise RuntimeError(f"Could not check repository: {response.status_code} {response.text[:800]}")

    payload = {
        "name": repo,
        "private": private,
        "description": "CRDT-Port Streamlit data visualisation dashboard demonstrator",
        "auto_init": False,
    }
    github_request(session, "POST", f"{API_ROOT}/user/repos", expected={201}, json=payload)
    print(f"Created repository: https://github.com/{owner}/{repo}")


def existing_file_sha(session: requests.Session, owner: str, repo: str, path: str) -> str | None:
    url = f"{API_ROOT}/repos/{owner}/{repo}/contents/{path}"
    response = session.get(url, timeout=30)
    if response.status_code == 404:
        return None
    if response.status_code != 200:
        raise RuntimeError(f"Could not check {path}: {response.status_code} {response.text[:800]}")
    payload = response.json()
    if isinstance(payload, dict):
        return payload.get("sha")
    return None


def upload_file(session: requests.Session, owner: str, repo: str, rel_path: str, message_prefix: str) -> None:
    path = BASE_DIR / rel_path
    if not path.exists():
        print(f"Skip missing file: {rel_path}")
        return

    content = base64.b64encode(path.read_bytes()).decode("ascii")
    sha = existing_file_sha(session, owner, repo, rel_path)
    payload: dict[str, Any] = {
        "message": f"{message_prefix}: {rel_path}",
        "content": content,
    }
    if sha:
        payload["sha"] = sha

    url = f"{API_ROOT}/repos/{owner}/{repo}/contents/{rel_path}"
    github_request(session, "PUT", url, expected={200, 201}, json=payload)
    print(f"Uploaded {rel_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Publish the dashboard to GitHub using a PAT in GITHUB_TOKEN.")
    parser.add_argument("--owner", default="HenryZhanggg")
    parser.add_argument("--repo", default=DEFAULT_REPO)
    parser.add_argument("--private", action="store_true", help="Create the repository as private.")
    parser.add_argument("--message-prefix", default="Publish CRDT-Port dashboard")
    args = parser.parse_args()

    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        raise SystemExit("Set GITHUB_TOKEN to a GitHub Personal Access Token before running this script.")

    session = make_session(token)
    user = github_request(session, "GET", f"{API_ROOT}/user", expected={200}).json()
    print(f"Authenticated as: {user.get('login')}")

    ensure_repo(session, args.owner, args.repo, args.private)
    for rel_path in FILES_TO_UPLOAD:
        upload_file(session, args.owner, args.repo, rel_path, args.message_prefix)

    print(json.dumps({"url": f"https://github.com/{args.owner}/{args.repo}"}, indent=2))


if __name__ == "__main__":
    main()
