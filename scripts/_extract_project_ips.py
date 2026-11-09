#!/usr/bin/env python3
"""Extract IPv4 addresses from project docs/configs (not node_modules/venv)."""
from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(r"C:\Users\roxan\Projects\TarGPT3")
IP_RE = re.compile(
    r"\b(?:(?:25[0-5]|2[0-4]\d|[01]?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|[01]?\d?\d)\b"
)
SKIP_DIR = {
    ".git",
    "venv",
    ".venv",
    "node_modules",
    "__pycache__",
    "deploy-backups",
    "backups",
    "static",
    "fonts",
    "_folai",
    "agent-tools",
}
SKIP_SUFFIX = {".png", ".jpg", ".jpeg", ".webp", ".mp4", ".woff", ".woff2", ".pyc", ".zip", ".tgz"}

OWN = {
    "37.46.18.192": "HSHP VPS (наш сервер)",
    "127.0.0.1": "localhost",
    "0.0.0.0": "bind all interfaces",
}

hits: dict[str, list[str]] = defaultdict(list)
for path in ROOT.rglob("*"):
    if not path.is_file():
        continue
    if any(p in SKIP_DIR for p in path.parts):
        continue
    if path.suffix.lower() in SKIP_SUFFIX:
        continue
    if path.stat().st_size > 2_000_000:
        continue
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        continue
    for ip in set(IP_RE.findall(text)):
        # skip fake/chrome versions like 120.0.0.0 from UA strings if alone — keep but tag
        rel = str(path.relative_to(ROOT)).replace("\\", "/")
        if rel not in hits[ip]:
            hits[ip].append(rel)

print("=== IP from project files ===")
for ip in sorted(hits, key=lambda x: (x not in OWN, x)):
    note = OWN.get(ip, "")
    files = ", ".join(hits[ip][:5])
    more = f" (+{len(hits[ip])-5})" if len(hits[ip]) > 5 else ""
    print(f"{ip:16}  {note:28}  {files}{more}")
print(f"\ntotal unique: {len(hits)}")
