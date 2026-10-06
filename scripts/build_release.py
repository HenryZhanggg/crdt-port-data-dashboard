"""Build a reproducible source package without credentials or generated caches."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
import zipfile

from publish_to_github_api import FILES_TO_UPLOAD

BASE = Path(__file__).resolve().parents[1]
OUTPUT = BASE / "outputs" / "2026-10-06"
OUTPUT.mkdir(parents=True, exist_ok=True)
extra = ["tests/test_data_quality.py", "tests/test_connector_dates.py", "tests/test_dashboard_views.py",
         "tests/capture_dashboard.py", "scripts/preview_dashboard.py", "scripts/build_release.py",
         "scripts/check_deployment_access.py", "docs/superpowers/plans/2026-10-06-monitoring-quality-visuals.md"]
files = sorted(set(FILES_TO_UPLOAD + extra))
missing = [name for name in files if not (BASE / name).is_file()]
if missing:
    raise SystemExit(f"Release inputs missing: {missing}")
manifest = {"built_at_utc": datetime.now(timezone.utc).isoformat(), "entry_point": "app.py",
    "cloud_status": "Source archive only; verify GitHub publication and cloud deployment separately",
    "files": {name: hashlib.sha256((BASE / name).read_bytes()).hexdigest() for name in files}}
archive = OUTPUT / "CRDT_dashboard_update_2026-10-06.zip"
with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as package:
    for name in files:
        package.write(BASE / name, name)
    package.writestr("release_manifest.json", json.dumps(manifest, indent=2))
with zipfile.ZipFile(archive) as package:
    assert package.testzip() is None
    assert not any("secrets.toml" in name or ".venv/" in name for name in package.namelist())
(OUTPUT / "release_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
print(json.dumps({"archive": str(archive), "files": len(files), "bytes": archive.stat().st_size}))
