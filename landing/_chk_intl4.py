import urllib.request

req = urllib.request.Request("https://followthefrensy.ru/", method="GET")
with urllib.request.urlopen(req, timeout=20) as r:
    print("status", r.status)
    print("server", r.headers.get("Server"))
    print("hsts", r.headers.get("Strict-Transport-Security"))
    print("csp", r.headers.get("Content-Security-Policy"))
    print("xfo", r.headers.get("X-Frame-Options"))
    print("xcto", r.headers.get("X-Content-Type-Options"))
    print("refpol", r.headers.get("Referrer-Policy"))
    print("perm", r.headers.get("Permissions-Policy"))
    print("setcookie", r.headers.get("Set-Cookie"))
    print("cache", r.headers.get("Cache-Control"))

for path in ("/robots.txt", "/security.txt", "/.well-known/security.txt", "/sitemap.xml"):
    try:
        u = urllib.request.urlopen("https://followthefrensy.ru" + path, timeout=10)
        print(path, u.status, u.read(80))
    except Exception as e:
        print(path, type(e).__name__, getattr(e, "code", e))
