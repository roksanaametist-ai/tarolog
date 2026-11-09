from pathlib import Path
import os
import urllib.request

for path, name in (
    ("https://followthefrensy.ru/", "home"),
    ("https://followthefrensy.ru/oferta", "oferta"),
    ("https://followthefrensy.ru/privacy", "privacy"),
):
    html = urllib.request.urlopen(path, timeout=20).read().decode("utf-8", "replace")
    keys = [
        "Для покупателя",
        "Самозанятая",
        "Алигайдеровна",
        "503225242801",
        "Robokassa",
        "Политика ПД",
        "оферта",
        "/privacy",
        "/oferta",
        "Возврат",
        "трансгранич",
        "price-card",
        "shell-cycle",
        "burn-overlay",
        "consent_pd",
        "consent_tb",
    ]
    print(name, len(html), {k: (k.lower() in html.lower() if k != "/privacy" else k in html) for k in keys})
    if name == "home":
        Path(os.environ["TEMP"], "frensy-home.html").write_text(html, encoding="utf-8")
