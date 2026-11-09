from pathlib import Path
import os

p = Path(os.environ["TEMP"]) / "frensy-home.html"
h = p.read_text(encoding="utf-8", errors="replace")
print("len", len(h))
print("price", h.count("price-card"))
print("jelly", "jelly" in h)
print("tiktok", "3 333" in h)
print("portal", 'id="portal"' in h)
print("v201", "main.css?v=201" in h)
print("error", "Traceback" in h or "jinja2" in h.lower())
