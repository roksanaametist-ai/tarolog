import re
import ssl
import urllib.parse
import urllib.request

CTX = ssl.create_default_context()
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"}
BASE = "https://pd.rkn.gov.ru/operators-registry/operators-list/"


def get(url: str) -> str:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=40, context=CTX) as r:
        return r.read().decode("utf-8", "replace")


def search(**params) -> str:
    q = urllib.parse.urlencode({"act": "search", **params}, encoding="utf-8")
    return get(BASE + "?" + q)


def snippet(html: str) -> str:
    m = re.search(r"</form>(.{0,400})", html, re.S)
    return re.sub(r"<[^>]+>", " ", m.group(1) if m else html[-400:])


def main() -> None:
    queries = [
        ("inn", {"inn": "503225242801", "name_full": "", "regn": ""}),
        ("fio", {"inn": "", "name_full": "Аметист Роксана Алигайдеровна", "regn": ""}),
        ("control", {"inn": "7736207543", "name_full": "Яндекс", "regn": ""}),
    ]
    for name, params in queries:
        html = search(**params)
        print("===", name)
        print(" notfound", "Записей не найдено" in html)
        um = re.search(r"Последнее изменение:\s*([0-9.]+ [0-9:]+)", html)
        cm = re.search(r"содержатся сведения о ([0-9 ]+) операторах", html)
        print(" last_change", um.group(1) if um else "?")
        print(" count", cm.group(1) if cm else "?")
        print(" after_form", " ".join(snippet(html).split())[:240])


if __name__ == "__main__":
    main()
