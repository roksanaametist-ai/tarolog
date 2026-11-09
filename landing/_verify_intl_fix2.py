import re
import urllib.request

h = urllib.request.urlopen("https://followthefrensy.ru/", timeout=20).read().decode("utf-8")
print("bytes", len(h))
print("18+", "\u0441\u0442\u0430\u0440\u0448\u0435 18 \u043b\u0435\u0442" in h)
print("fonts.css", "fonts.css" in h)
print("google_css_link", bool(re.search(r"<link[^>]+fonts\.googleapis", h)))
print("gstatic_url", "https://fonts.gstatic.com" in h)
print("lead_form", "lead-form" in h)
print("en_US", "en_US" in h)
print("hsts-check via headers")
req = urllib.request.Request("https://followthefrensy.ru/")
with urllib.request.urlopen(req, timeout=20) as r:
    print("HSTS", r.headers.get("Strict-Transport-Security"))
    print("XFO", r.headers.get("X-Frame-Options"))

# third-party hosts in src/href
hosts = set(re.findall(r"https://([^/\"']+)", h))
print("https_hosts", sorted(hosts))
needle = "\u0441\u0442\u0430\u0440\u0448\u0435 18"
i = h.find(needle)
print("age_ctx", h[i : i + 80] if i >= 0 else "MISSING")
