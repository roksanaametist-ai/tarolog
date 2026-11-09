import urllib.request

h = urllib.request.urlopen("https://followthefrensy.ru/", timeout=20).read().decode("utf-8", "replace")
checks = [
    "fonts.googleapis",
    "gstatic",
    "consent_pd",
    "consent_tb",
    "lead-form",
    "hreflang",
    "en_US",
    "shell-cycle",
    "/privacy",
    "/oferta",
    "metrika",
    "gtag",
    "cloudflare",
    "show_lead",
]
for c in checks:
    print(c, c in h)
print("has_lang_ru", "lang=\"ru\"" in h)
print("bytes", len(h))
