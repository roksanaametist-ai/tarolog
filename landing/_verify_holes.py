# -*- coding: utf-8 -*-
import json
import urllib.request

base = "http://127.0.0.1:5002"

def get(path):
    with urllib.request.urlopen(base + path, timeout=20) as r:
        return r.read().decode("utf-8", "replace")

home = get("/")
print("home form", "consent_pd" in home, "consent_tb" in home)
print("home lead_include", "lead-title" in home)

qf = get("/?lead_form=1")
print("flag form", "consent_pd" in qf, "consent_tb" in qf, "consent_oferta" in qf)

pr = get("/privacy")
print("privacy DE", "Германии" in pr, "100463957" in pr, "IP-адрес" in pr)
print("privacy form-claim", "форма на сайте, кнопки" in pr)

of = get("/oferta")
print("oferta bot-start-use", "начало использования бота после" in of)
print("oferta form-if", "если форма показана" in of)

req = urllib.request.Request(
    base + "/api/lead",
    data=json.dumps({"name": "Тест", "contact": "@x", "consent_pd": True, "consent_oferta": True}).encode(),
    headers={"Content-Type": "application/json"},
    method="POST",
)
try:
    urllib.request.urlopen(req, timeout=20)
    print("api missing tb unexpected ok")
except Exception as e:
    print("api missing tb", getattr(e, "code", None), getattr(e, "read", lambda: b"")()[:200])
