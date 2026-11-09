import re
import ssl
import urllib.parse
import urllib.request

CTX = ssl.create_default_context()
UA = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}


def get(url: str) -> tuple[int, str, str]:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=30, context=CTX) as r:
        raw = r.read()
        return r.status, r.headers.get("Content-Type", ""), raw.decode("utf-8", "replace")


def peek(html: str, *needles: str) -> None:
    print("len", len(html))
    for n in needles:
        print(" ", n, n.lower() in html.lower())
    caps = re.findall(r"captcha|код с картинк|g-recaptcha|smartcaptcha", html, re.I)
    print(" captcha_hits", len(caps), caps[:5])
    inputs = re.findall(r'<input[^>]+name=["\']([^"\']+)', html, re.I)
    print(" inputs", inputs[:20])


def main() -> None:
    print("=== OPERATORS LIST ===")
    st, ct, html = get("https://pd.rkn.gov.ru/operators-registry/operators-list/")
    print("status", st, ct)
    peek(html, "ИНН", "наименование", "Аметист", "форма")

    print("=== OP NOTIF CHECK ===")
    st, ct, html = get("https://pd.rkn.gov.ru/operators-registry/notification_check/")
    print("status", st)
    peek(html, "номер", "ключ", "статус")

    print("=== TB NOTIF CHECK ===")
    st, ct, html = get("https://pd.rkn.gov.ru/cross-border-transmission/notification_check/")
    print("status", st)
    peek(html, "номер", "ключ", "статус", "Получено")


if __name__ == "__main__":
    main()
