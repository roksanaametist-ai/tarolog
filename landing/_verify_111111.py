# -*- coding: utf-8 -*-
import urllib.request
from pathlib import Path

root = Path("/root/tarolog/landing")
idx = (root / "templates/index.html").read_text(encoding="utf-8")
print("idx 111 111", idx.count("111 111"))
print("css", [ln.strip() for ln in idx.splitlines() if "main.css" in ln][:4])
html = urllib.request.urlopen("http://127.0.0.1:5002/").read().decode("utf-8", "replace")
print("live 111 111", html.count("111 111"), "111111", html.count("111111"), "sums", html.count("price-card__sum"))
of = urllib.request.urlopen("http://127.0.0.1:5002/oferta").read().decode("utf-8", "replace")
print("oferta 111 111", of.count("111 111"))
