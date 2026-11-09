# Self-host fonts, 18+, drop Google/en_US, close lead form on EU host.
from __future__ import annotations

import os
import re
from pathlib import Path

ROOT = Path(os.environ.get("LEGAL_LANDING_ROOT", "/root/tarolog/landing"))
ENV_FILE = Path(os.environ.get("LEGAL_ENV_FILE", "/root/tarolog/.env"))
SITE = ROOT / "SiteApp.py"

GOOGLE_BLOCK = re.compile(
    r"[ \t]*<link rel=\"preconnect\" href=\"https://fonts\.googleapis\.com\">\s*"
    r"<link rel=\"preconnect\" href=\"https://fonts\.gstatic\.com\" crossorigin>\s*"
    r"<link href=\"https://fonts\.googleapis\.com/css2\?family=[^\"]+\" rel=\"stylesheet\">\s*",
    re.I,
)
FONTS_LINK = '    <link rel="stylesheet" href="{{ url_for(\'static\', filename=\'css/fonts.css\') }}?v=1">\n'
EN_US = '    <meta property="og:locale:alternate" content="en_US">\n'
FOOT_OLD = (
    '                <p class="jelly-foot__legal">Самозанятая {{ operator_name }} '
    '· ИНН {{ operator_inn }} · {{ operator_city }}</p>\n'
)
FOOT_NEW = (
    '                <p class="jelly-foot__legal">Самозанятая {{ operator_name }} '
    '· ИНН {{ operator_inn }} · {{ operator_city }}</p>\n'
    '                <p class="jelly-foot__legal">Сайт и услуги для лиц старше 18 лет. '
    'Консультация, не медицина и не гарантия событий в жизни.</p>\n'
)
LEAD_FN_OLD = """# Local default: show. Prod deploy will set LANDING_SHOW_LEAD_FORM=0.
def _lead_form_enabled() -> bool:
    q = (request.args.get("lead_form") or request.args.get("lead") or "").strip().lower()
    if q in ("1", "true", "on", "yes"):
        return True
    if q in ("0", "false", "off", "no"):
        return False
    return os.getenv("LANDING_SHOW_LEAD_FORM", "1").strip().lower() in ("1", "true", "on", "yes")
"""
LEAD_FN_NEW = """def _lead_form_enabled() -> bool:
    return os.getenv("LANDING_SHOW_LEAD_FORM", "0").strip().lower() in ("1", "true", "on", "yes")
"""
API_OLD = '''@app.route("/api/lead", methods=["POST"])
def submit_lead():
    if request.content_length and request.content_length > 16_384:
'''
API_NEW = '''@app.route("/api/lead", methods=["POST"])
def submit_lead():
    if not _lead_form_enabled():
        return jsonify({"ok": False, "error": "Форма заявки сейчас закрыта. Напишите в Telegram."}), 403
    if request.content_length and request.content_length > 16_384:
'''
NGINX_HEADERS = """
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Content-Type-Options nosniff always;
    add_header X-Frame-Options SAMEORIGIN always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    add_header Permissions-Policy "camera=(), microphone=(), geolocation=()" always;
"""


def patch_text(path: Path, old: str, new: str, label: str) -> None:
    text = path.read_text(encoding="utf-8")
    if new in text and old not in text:
        print("skip", label)
        return
    if old not in text:
        raise SystemExit(f"missing {label} in {path}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    print("ok", label)


def patch_templates() -> None:
    n_fonts = n_en = n_foot = 0
    for path in sorted((ROOT / "templates").glob("*.html")):
        text = path.read_text(encoding="utf-8")
        orig = text
        if re.search(r"<link[^>]+fonts\.(googleapis|gstatic)\.com", text, re.I):
            text, k = GOOGLE_BLOCK.subn(FONTS_LINK, text)
            if k == 0:
                raise SystemExit(f"google fonts still in {path}")
            n_fonts += k
        if EN_US in text:
            text = text.replace(EN_US, "", 1)
            n_en += 1
        if FOOT_OLD in text and "старше 18 лет" not in text:
            text = text.replace(FOOT_OLD, FOOT_NEW, 1)
            n_foot += 1
        if text != orig:
            path.write_text(text, encoding="utf-8")
            print("html", path.name)
    leftover = []
    link_re = re.compile(r"<link[^>]+fonts\.(googleapis|gstatic)\.com", re.I)
    for path in (ROOT / "templates").glob("*.html"):
        t = path.read_text(encoding="utf-8")
        if link_re.search(t):
            leftover.append(path.name)
    if leftover:
        raise SystemExit("fonts leftover " + ",".join(leftover))
    print("fonts_replaced", n_fonts, "en_us_dropped", n_en, "age18", n_foot)


def patch_siteapp() -> None:
    t = SITE.read_text(encoding="utf-8")
    if LEAD_FN_NEW.strip() in t and "lead_form=1" not in t:
        print("skip leadfn")
    else:
        if LEAD_FN_OLD not in t:
            raise SystemExit("missing lead fn")
        t = t.replace(LEAD_FN_OLD, LEAD_FN_NEW, 1)
        print("ok leadfn")
    if "Форма заявки сейчас закрыта" in t:
        print("skip leadapi")
    else:
        if API_OLD not in t:
            raise SystemExit("missing lead api")
        t = t.replace(API_OLD, API_NEW, 1)
        print("ok leadapi")
    SITE.write_text(t, encoding="utf-8")


def patch_env() -> None:
    if not ENV_FILE.exists():
        print("skip env missing")
        return
    text = ENV_FILE.read_text(encoding="utf-8")
    new, n = re.subn(
        r"^LANDING_SHOW_LEAD_FORM=.*$",
        "LANDING_SHOW_LEAD_FORM=0",
        text,
        count=1,
        flags=re.M,
    )
    if n == 0:
        new = text.rstrip() + "\nLANDING_SHOW_LEAD_FORM=0\n"
        n = -1
    ENV_FILE.write_text(new, encoding="utf-8")
    print("ok env_lead", n)


def patch_nginx(conf: Path) -> None:
    if not conf.exists():
        print("skip nginx missing", conf)
        return
    text = conf.read_text(encoding="utf-8")
    if "Strict-Transport-Security" in text:
        print("skip nginx already", conf)
        return
    marker = "ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem; # managed by Certbot"
    if marker in text:
        text = text.replace(marker, marker + "\n" + NGINX_HEADERS.rstrip("\n"), 1)
    else:
        marker2 = "ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;"
        if marker2 not in text:
            raise SystemExit(f"nginx marker missing {conf}")
        text = text.replace(marker2, marker2 + "\n" + NGINX_HEADERS.rstrip("\n"), 1)
    deck = """        add_header Cache-Control "public, max-age=604800";
        add_header X-Content-Type-Options nosniff;"""
    deck_new = """        add_header Cache-Control "public, max-age=604800";
        add_header X-Content-Type-Options nosniff;
        add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
        add_header X-Frame-Options SAMEORIGIN always;
        add_header Referrer-Policy "strict-origin-when-cross-origin" always;"""
    if deck in text:
        text = text.replace(deck, deck_new, 1)
        print("ok nginx deck headers")
    conf.write_text(text, encoding="utf-8")
    print("ok nginx", conf)


def main() -> None:
    fonts = ROOT / "static" / "css" / "fonts.css"
    if not fonts.exists():
        raise SystemExit("fonts.css missing — copy static/css/fonts.css and static/fonts first")
    patch_templates()
    patch_siteapp()
    patch_env()
    nginx = Path(os.environ.get("LEGAL_NGINX_CONF", "/etc/nginx/sites-enabled/default"))
    patch_nginx(nginx)


if __name__ == "__main__":
    main()
