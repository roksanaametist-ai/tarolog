"""Download OFL webfonts used by the site and write local @font-face CSS."""
from __future__ import annotations

import hashlib
import re
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FONT_DIR = ROOT / "static" / "fonts"
CSS_PATH = ROOT / "static" / "css" / "fonts.css"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
FAMILIES = [
    "https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,400;0,500;0,600;1,400;1,500&display=swap",
    "https://fonts.googleapis.com/css2?family=Syne:wght@400;600;800&display=swap",
]
LICENSE_URLS = [
    (
        "https://raw.githubusercontent.com/google/fonts/main/ofl/cormorantgaramond/OFL.txt",
        "OFL-CormorantGaramond.txt",
    ),
    (
        "https://raw.githubusercontent.com/google/fonts/main/ofl/syne/OFL.txt",
        "OFL-Syne.txt",
    ),
]


def fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read()


def main() -> None:
    FONT_DIR.mkdir(parents=True, exist_ok=True)
    css_out: list[str] = [
        "/* Self-hosted OFL fonts. Do not load fonts.googleapis.com / fonts.gstatic.com. */",
        "",
    ]
    used_names: set[str] = set()
    for css_url in FAMILIES:
        css = fetch(css_url).decode("utf-8")
        blocks = re.split(r"(?=@font-face\s*\{)", css)
        for block in blocks:
            if "@font-face" not in block:
                continue
            src_m = re.search(r"url\((https://fonts\.gstatic\.com/[^)]+)\)", block)
            if not src_m:
                continue
            remote = src_m.group(1).strip("\"'")
            digest = hashlib.sha1(remote.encode()).hexdigest()[:10]
            fam_m = re.search(r"font-family:\s*'([^']+)'", block)
            style_m = re.search(r"font-style:\s*(\w+)", block)
            weight_m = re.search(r"font-weight:\s*(\d+)", block)
            comment_m = re.search(r"/\*\s*([^*]+?)\s*\*/", block)
            fam = (fam_m.group(1) if fam_m else "font").replace(" ", "").lower()
            style = style_m.group(1) if style_m else "normal"
            weight = weight_m.group(1) if weight_m else "400"
            subset = (comment_m.group(1) if comment_m else "latin").strip().replace(" ", "-")
            name = f"{fam}-{subset}-{weight}-{style}-{digest}.woff2"
            if name in used_names:
                continue
            used_names.add(name)
            dest = FONT_DIR / name
            if not dest.exists():
                dest.write_bytes(fetch(remote))
            local_block = block.replace(src_m.group(0), f"url(../fonts/{name})")
            css_out.append(local_block.strip())
            css_out.append("")
            print("ok", name, dest.stat().st_size)
    CSS_PATH.write_text("\n".join(css_out).rstrip() + "\n", encoding="utf-8")
    for url, fname in LICENSE_URLS:
        (FONT_DIR / fname).write_bytes(fetch(url))
        print("license", fname)
    print("css", CSS_PATH, "faces", len(used_names))


if __name__ == "__main__":
    main()
