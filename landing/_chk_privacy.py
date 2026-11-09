import urllib.request
p = urllib.request.urlopen("https://followthefrensy.ru/privacy", timeout=20).read().decode("utf-8")
keys = [
    "26.10.2026",
    "Cookie",
    "fonts.googleapis.com",
    "Cormorant",
    "Robokassa",
    "\u0447\u0430\u0435\u0432",
    "HSTS",
    "\u0415\u0432\u0440\u043e\u043f\u0435\u0439\u0441\u043a",
    "fonts.css",
    "<link",
]
for k in keys:
    print(k[:40], k in p)
print("google_link", "fonts.googleapis.com/css" in p)
print("len", len(p))
