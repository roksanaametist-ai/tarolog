# -*- coding: utf-8 -*-
from pathlib import Path

p = Path("/root/tarolog/landing/legal_pages.py")
t = p.read_text(encoding="utf-8")
t = t.replace('PRIVACY_EDITION = "16.10.2026"', 'PRIVACY_EDITION = "17.10.2026"')
t = t.replace('OFERTA_EDITION = "16.10.2026"', 'OFERTA_EDITION = "17.10.2026"')
p.write_text(t, encoding="utf-8")
root = Path("/root/tarolog/landing/templates")
hits = []
for f in sorted(root.glob("*.html")):
    s = f.read_text(encoding="utf-8")
    if "самозанят" in s.lower() or "909-74-37" in s or "operator_phone" in s or "operator_email" in s:
        hits.append(f.name)
print("editions ok, leftover templates", hits or "none")
