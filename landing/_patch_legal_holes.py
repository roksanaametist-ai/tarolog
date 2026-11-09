# -*- coding: utf-8 -*-
from pathlib import Path

ROOT = Path("/root/tarolog/landing")

idx = ROOT / "templates" / "index.html"
t = idx.read_text(encoding="utf-8")
needle = """            <section
                class="contacts{% if jelly_hero %} jelly-stage jelly-stage--copy-left{% endif %}"
                id="contacts"
"""
insert = """            {% if show_lead_form %}
            {% include "_lead_form.html" %}
            {% endif %}

            <section
                class="contacts{% if jelly_hero %} jelly-stage jelly-stage--copy-left{% endif %}"
                id="contacts"
"""
if "{% include \"_lead_form.html\" %}" not in t:
    if needle not in t:
        raise SystemExit("contacts block not found")
    t = t.replace(needle, insert, 1)
t = t.replace(
    "Три формата — от одного расклада до полного решения.",
    "Три формата — от одного расклада до полного разбора.",
)
t = t.replace("js/lead-form.js') }}?v=2", "js/lead-form.js') }}?v=3")
idx.write_text(t, encoding="utf-8")

app = ROOT / "SiteApp.py"
a = app.read_text(encoding="utf-8")
old = """    consent = payload.get("consent") in (True, 1, "1", "true", "yes", "on")
    consent_pd = payload.get("consent_pd") in (True, 1, "1", "true", "yes", "on") or consent
    consent_oferta = payload.get("consent_oferta") in (True, 1, "1", "true", "yes", "on")
"""
new = """    consent_pd = payload.get("consent_pd") in (True, 1, "1", "true", "yes", "on")
    consent_tb = payload.get("consent_tb") in (True, 1, "1", "true", "yes", "on")
    consent_oferta = payload.get("consent_oferta") in (True, 1, "1", "true", "yes", "on")
"""
if old not in a:
    raise SystemExit("api consents not found")
a = a.replace(old, new, 1)
old2 = """    if not consent_oferta:
        return jsonify({"ok": False, "error": "Нужно принять оферту"}), 400
"""
new2 = """    if not consent_tb:
        return jsonify({"ok": False, "error": "Нужно согласие на трансграничную передачу"}), 400
    if not consent_oferta:
        return jsonify({"ok": False, "error": "Нужно принять оферту"}), 400
"""
if old2 not in a:
    raise SystemExit("oferta check not found")
a = a.replace(old2, new2, 1)
a = a.replace(
    '"consent_pd": True,\n        "consent_oferta": True,',
    '"consent_pd": True,\n        "consent_tb": True,\n        "consent_oferta": True,',
    1,
)
app.write_text(a, encoding="utf-8")
print("landing patched", "lead_include", '_lead_form.html' in idx.read_text(encoding="utf-8"))
