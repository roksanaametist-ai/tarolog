import re
import ssl
import urllib.parse
import urllib.request

CTX = ssl.create_default_context()
UA = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}


def fetch(url: str, data: bytes | None = None) -> str:
    req = urllib.request.Request(url, data=data, headers=UA)
    with urllib.request.urlopen(req, timeout=40, context=CTX) as r:
        return r.read().decode("utf-8", "replace")


def main() -> None:
    html = fetch("https://pd.rkn.gov.ru/operators-registry/operators-list/")
    forms = re.findall(r"<form[^>]+>", html, re.I)
    print("forms", forms)
    # save snippet around form
    i = html.lower().find("<form")
    print(html[i : i + 1800])
    print("==== SEARCH INN ====")
    payload = urllib.parse.urlencode(
        {"act": "search", "name_full": "", "inn": "503225242801", "regn": ""}
    ).encode()
    res = fetch("https://pd.rkn.gov.ru/operators-registry/operators-list/", payload)
    print("len", len(res))
    for n in ["не найден", "не найдены", "Аметист", "503225242801", "результат", "записей"]:
        print(n, n.lower() in res.lower())
    # table-ish
    texts = re.findall(r"<td[^>]*>(.*?)</td>", res, re.I | re.S)
    print("tds", len(texts), [re.sub("<[^>]+>", "", t)[:80] for t in texts[:12]])
    if "не найден" in res.lower() or "не найдены" in res.lower():
        m = re.search(r".{0,80}не найден.{0,80}", res, re.I | re.S)
        print("miss", m.group(0) if m else "")

    print("==== SEARCH NAME ====")
    payload = urllib.parse.urlencode(
        {
            "act": "search",
            "name_full": "Аметист Роксана Алигайдеровна",
            "inn": "",
            "regn": "",
        }
    ).encode()
    res2 = fetch("https://pd.rkn.gov.ru/operators-registry/operators-list/", payload)
    print("len", len(res2))
    for n in ["не найден", "Аметист", "Роксана", "503225242801"]:
        print(n, n.lower() in res2.lower())
    texts = re.findall(r"<td[^>]*>(.*?)</td>", res2, re.I | re.S)
    print("tds", len(texts), [re.sub("<[^>]+>", "", t)[:100] for t in texts[:20]])


if __name__ == "__main__":
    main()
