"""Check existing GitHub authentication without displaying or storing credentials."""
import os
import subprocess

import requests


def authenticated_session():
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        environment = dict(os.environ, GIT_TERMINAL_PROMPT="0", GCM_INTERACTIVE="never", GCM_GUI_PROMPT="false")
        try:
            result = subprocess.run(["git", "credential", "fill"], input="protocol=https\nhost=github.com\n\n",
                capture_output=True, text=True, timeout=20, env=environment)
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return None
        fields = dict(line.split("=", 1) for line in result.stdout.splitlines() if "=" in line)
        token = fields.get("password") if result.returncode == 0 else None
    if not token:
        return None
    session = requests.Session()
    session.headers.update({"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"})
    return session


if __name__ == "__main__":
    session = authenticated_session()
    if session is None:
        print("No non-interactive GitHub credential is available.")
    else:
        response = session.get("https://api.github.com/repos/HenryZhanggg/crdt-port-data-dashboard", timeout=20)
        print({"repository_access": response.status_code == 200, "push_permission": response.json().get("permissions", {}).get("push", False)})
