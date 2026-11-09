import urllib.request
import ssl

ctx = ssl.create_default_context()
pages = ["/", "/privacy", "/oferta"]
for path in pages:
    req = urllib.request.Request(
        "https://followthefrensy.ru" + path,
        headers={"User-Agent": "Mozilla/5.0 (audit)"},
    )
    with urllib.request.urlopen(req, timeout=25, context=ctx) as r:
        html = r.read().decode("utf-8", "replace")
        hdrs = dict(r.headers)
    keys = [
        "cookie",
        "Cookie",
        "GDPR",
        "GDPR",
        "18",
        "Impressum",
        "cookie-banner",
        "Яндекс.Метрика",
        "gtag",
        "google-analytics",
        "Facebook",
        "consent",
        "согласие",
        "Герман",
        "OpenAI",
        "Telegram",
        "Robokassa",
        "чаевые",
        "поддержка",
        "возврат",
        "комисси",
        "самозанят",
        "Алигайдеровна",
        "roxanaametist@gmail.com",
        "100463957",
        "IXcellerate",
        "крипт",
        "PayPal",
        "Stripe",
        "age",
        "cookies",
    ]
    print("===", path, "len", len(html), "status ok")
    for k in [
        "Герман",
        "IXcellerate",
        "100463957",
        "OpenAI",
        "Robokassa",
        "чаевые",
        "Добровольная поддержка",
        "cookie",
        "Cookie",
        "Метрик",
        "gtag",
        "18 лет",
        "Impressum",
        "GDPR",
        "DSGVO",
        "право на удаление",
        "Роскомнадзор",
        "Алигайдеровна",
        "gmail.com",
        "возврат",
    ]:
        print(f"  {k!r}: {k in html}")
    print("  server:", hdrs.get("Server"), "set-cookie:", hdrs.get("Set-Cookie"))
    print("  csp:", bool(hdrs.get("Content-Security-Policy")))
    print("  hsts:", bool(hdrs.get("Strict-Transport-Security")))
