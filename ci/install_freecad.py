#!/usr/bin/env python3
"""Fetch the official pinned FreeCAD AppImage, verify its bytes, then extract without FUSE."""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
LOCK = ROOT / "ci/freecad-lock.json"
RUNTIME = ROOT / ".runtime/freecad"


def main():
    spec = json.loads(LOCK.read_text(encoding="utf-8"))
    version = spec["version"]
    assert re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", version)
    name = f"FreeCAD_{version}-Linux-x86_64-py311.AppImage"
    url = f"https://github.com/FreeCAD/FreeCAD/releases/download/{version}/{name}"
    if name != spec["asset_name"] or url != spec["url"]:
        raise ValueError("Unapproved download destination")
    if not re.fullmatch(r"[a-f0-9]{64}", spec["sha256"]):
        raise ValueError("Invalid SHA-256 lock")
    limit = spec["size_bytes"]
    if not isinstance(limit, int) or not 100_000_000 < limit < 2_000_000_000:
        raise ValueError("Invalid pinned size")
    RUNTIME.mkdir(parents=True, exist_ok=False)
    destination = RUNTIME / name
    digest = hashlib.sha256()
    size = 0
    request = urllib.request.Request(url, headers={"User-Agent": "DOM-FreeCAD-synthetic-QA"})
    with urllib.request.urlopen(request, timeout=120) as response, destination.open("xb") as out:
        for chunk in iter(lambda: response.read(1024 * 1024), b""):
            size += len(chunk)
            if size > limit:
                raise ValueError("Unexpected asset size")
            digest.update(chunk)
            out.write(chunk)
    if size != limit or digest.hexdigest() != spec["sha256"]:
        raise ValueError("Official FreeCAD binary verification FAILED")
    destination.chmod(0o755)
    with (RUNTIME / "extraction.log").open("wb") as log:
        subprocess.run([str(destination), "--appimage-extract"], cwd=RUNTIME,
                       stdout=log, stderr=subprocess.STDOUT, check=True, timeout=300)
    app = RUNTIME / "squashfs-root/AppRun"
    if not app.is_file():
        raise ValueError("No extracted FreeCAD AppRun")
    print(f"VERIFIED FreeCAD {version}; {size} bytes; SHA256 {digest.hexdigest()}")
    print(f"EXTRACTED {app}")


if __name__ == "__main__":
    main()
