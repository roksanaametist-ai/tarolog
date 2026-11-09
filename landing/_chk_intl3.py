import re
import urllib.request

h = urllib.request.urlopen("https://followthefrensy.ru/", timeout=20).read().decode("utf-8", "replace")

# fonts
for m in re.finditer(r'(fonts\.googleapis[^"\']+|gstatic[^"\']+)', h):
    print("FONT", m.group(1)[:120])

# hreflang
for m in re.finditer(r'hreflang=["\'][^"\']+', h):
    print("HREFLANG", m.group(0))

# lead form
print("lead-form class", "class=\"lead-form" in h or "id=\"lead" in h)
print("LANDING_SHOW", "lead-wrap" in h, "display:none" in h[h.find("lead"):h.find("lead")+400] if "lead" in h else "nolead")
idx = h.find("lead-form")
print("around lead-form:", repr(h[max(0, idx-80):idx+200])[:280])

# consent
for m in re.finditer(r"consent_[a-z]+", h):
    pass
print("consent_pd count", h.count("consent_pd"))
print("consent_tb count", h.count("consent_tb"))
print("cookie", "cookie" in h.lower() or "куки" in h.lower() or "cookie" in h)
print("GDPR", "GDPR" in h)
print("18+", "18+" in h or "18 лет" in h)

p = urllib.request.urlopen("https://followthefrensy.ru/privacy", timeout=20).read().decode("utf-8", "replace")
print("---privacy---")
for k in [
    "Google Fonts",
    "googleapis",
    "cookie",
    "куки",
    "GDPR",
    "Евросоюз",
    "Германия",
    "OpenAI",
    "Robokassa",
    "крипт",
    "чаевые",
    "поддержк",
    "Cloudflare",
]:
    print(k, k.lower() in p.lower())
