# -*- coding: utf-8 -*-
from pathlib import Path
import sys

app = Path(sys.argv[1]) / "SiteApp.py"
a = app.read_text(encoding="utf-8")
old = (
    '    consent = payload.get("consent") in (True, 1, "1", "true", "yes", "on")\n'
    '    consent_pd = payload.get("consent_pd") in (True, 1, "1", "true", "yes", "on") or consent\n'
    '    consent_oferta = payload.get("consent_oferta") in (True, 1, "1", "true", "yes", "on")\n'
)
new = (
    '    consent_pd = payload.get("consent_pd") in (True, 1, "1", "true", "yes", "on")\n'
    '    consent_tb = payload.get("consent_tb") in (True, 1, "1", "true", "yes", "on")\n'
    '    consent_oferta = payload.get("consent_oferta") in (True, 1, "1", "true", "yes", "on")\n'
)
if old not in a:
    raise SystemExit("consent block missing")
a = a.replace(old, new, 1)
old2 = (
    '    if not consent_oferta:\n'
    '        return jsonify({"ok": False, "error": "Нужно принять оферту"}), 400\n'
)
new2 = (
    '    if not consent_tb:\n'
    '        return jsonify({"ok": False, "error": "Нужно согласие на трансграничную передачу"}), 400\n'
    '    if not consent_oferta:\n'
    '        return jsonify({"ok": False, "error": "Нужно принять оферту"}), 400\n'
)
if old2 not in a:
    raise SystemExit("oferta check missing")
a = a.replace(old2, new2, 1)
a = a.replace(
    '"consent_pd": True,\n        "consent_oferta": True,',
    '"consent_pd": True,\n        "consent_tb": True,\n        "consent_oferta": True,',
    1,
)
app.write_text(a, encoding="utf-8")
print("api tb ok")
