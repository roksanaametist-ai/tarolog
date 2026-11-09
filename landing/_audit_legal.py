# -*- coding: utf-8 -*-
import urllib.request
import json

base = "http://127.0.0.1:5002"
needles = [
    "самозанят",
    "909-74-37",
    "gmail.com",
    "111 111",
    "consent_pd",
    "consent_oferta",
    "ИНН",
    "152-ФЗ",
    "трансгранич",
    "18 лет",
    "оферт",
    "политик",
    "Мой налог",
    "3 333",
    "11 111",
    "1 111",
]


def get(path):
    req = urllib.request.Request(base + path, headers={"User-Agent": "audit"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.status, r.read().decode("utf-8", "replace")


for path in ("/", "/privacy", "/oferta"):
    status, t = get(path)
    print("====", path, status, "chars", len(t))
    low = t.lower()
    for s in needles:
        print(f"  {s}: {low.count(s.lower())}")

print("==== POST lead missing consents")
req = urllib.request.Request(
    base + "/api/lead",
    data=json.dumps({"name": "Тест", "contact": "@test"}).encode(),
    headers={"Content-Type": "application/json"},
    method="POST",
)
try:
    with urllib.request.urlopen(req, timeout=20) as r:
        print("unexpected", r.status, r.read()[:300])
except Exception as e:
    body = getattr(getattr(e, "file", None), "read", lambda: b"")()
    print(type(e).__name__, getattr(e, "code", None), body[:400])
