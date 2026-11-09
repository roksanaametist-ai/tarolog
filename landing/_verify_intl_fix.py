import json
import ssl
import urllib.error
import urllib.request

CTX = ssl.create_default_context()
UA = {"User-Agent": "Mozilla/5.0 intl-audit"}


def get(url: str):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=20, context=CTX) as r:
        return r.status, dict(r.headers), r.read()


def main() -> None:
    status, headers, raw = get("https://followthefrensy.ru/")
    html = raw.decode("utf-8", "replace")
    hsts = headers.get("Strict-Transport-Security") or headers.get("strict-transport-security")
    print("home", status, "bytes", len(html))
    print("hsts", hsts)
    print("xfo", headers.get("X-Frame-Options") or headers.get("x-frame-options"))
    print("xcto", headers.get("X-Content-Type-Options") or headers.get("x-content-type-options"))
    print("refpol", headers.get("Referrer-Policy") or headers.get("referrer-policy"))
    checks = {
        "googleapis_link": "fonts.googleapis.com" in html and "<link" in html[html.find("fonts.googleapis") - 80 : html.find("fonts.googleapis") + 20] if "fonts.googleapis.com" in html else False,
        "gstatic": "fonts.gstatic.com" in html,
        "fonts.css": "fonts.css" in html,
        "en_US": "en_US" in html,
        "age18": "18 лет" in html,
        "lead_form": "class=\"lead-form\"" in html or "name=\"consent_pd\"" in html,
        "privacy_link": "/privacy" in html,
        "oferta_link": "/oferta" in html,
    }
    print("home_checks", json.dumps(checks, ensure_ascii=False))

    pst, ph, praw = get("https://followthefrensy.ru/privacy")
    phtml = praw.decode("utf-8", "replace")
    print("privacy", pst, "edition", "26.10.2026" in phtml, "cookies", "Cookie" in phtml or "cookie" in phtml.lower(), "fonts_self", "followthefrensy.ru" in phtml and "gstatic" in phtml)

    req = urllib.request.Request(
        "https://followthefrensy.ru/api/lead",
        data=b'{"name":"Test","contact":"@x","consent_pd":1,"consent_tb":1,"consent_oferta":1}',
        headers={**UA, "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=20, context=CTX) as r:
            print("lead_api", r.status, r.read()[:200])
    except urllib.error.HTTPError as e:
        print("lead_api", e.code, e.read()[:200])

    fst, fh, fraw = get("https://followthefrensy.ru/static/css/fonts.css?v=1")
    fcss = fraw.decode("utf-8", "replace")
    print("fonts.css", fst, "bytes", len(fcss), "gstatic", "gstatic" in fcss, "woff2", "woff2" in fcss)

    # one actual font file from css
    import re
    m = re.search(r"url\((?:\.\./fonts/)?([^)]+\.woff2)\)", fcss)
    if m:
        name = m.group(1).split("/")[-1]
        ust, uh, uraw = get(f"https://followthefrensy.ru/static/fonts/{name}")
        print("woff2", name, ust, "bytes", len(uraw), "ctype", uh.get("Content-Type") or uh.get("content-type"))

    rst, rh, rraw = get("https://followthefrensy.ru/reading")
    rhtml = rraw.decode("utf-8", "replace")
    print("reading", rst, "googleapis", "fonts.googleapis.com" in rhtml, "fonts.css", "fonts.css" in rhtml)


if __name__ == "__main__":
    main()
