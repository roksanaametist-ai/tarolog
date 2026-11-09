import re
import ssl
import urllib.parse
import urllib.request
from pathlib import Path

CTX = ssl.create_default_context()
UA = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}
OUT = Path(r"C:\Users\roxan\Projects\TarGPT3\landing\_rkn_out")
OUT.mkdir(exist_ok=True)


def get(url: str) -> str:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=40, context=CTX) as r:
        return r.read().decode("utf-8", "replace")


def strip(html: str) -> str:
    t = re.sub(r"<script[\s\S]*?</script>", " ", html, flags=re.I)
    t = re.sub(r"<style[\s\S]*?</style>", " ", t, flags=re.I)
    t = re.sub(r"<[^>]+>", " ", t)
    t = re.sub(r"\s+", " ", t)
    return t.strip()


def search(**params) -> str:
    q = urllib.parse.urlencode({"act": "search", **params}, encoding="utf-8")
    url = "https://pd.rkn.gov.ru/operators-registry/operators-list/?" + q
    print("GET", url)
    return get(url)


def main() -> None:
    queries = {
        "inn": {"inn": "503225242801", "name_full": "", "regn": ""},
        "fio": {"inn": "", "name_full": "Аметист Роксана Алигайдеровна", "regn": ""},
        "fio2": {"inn": "", "name_full": "Аметист Роксана", "regn": ""},
        "patronym": {"inn": "", "name_full": "Алигайдеровна", "regn": ""},
        "follow": {"inn": "", "name_full": "Follow the Frensy", "regn": ""},
    }
    for name, params in queries.items():
        html = search(**params)
        (OUT / f"{name}.html").write_text(html, encoding="utf-8")
        text = strip(html)
        (OUT / f"{name}.txt").write_text(text, encoding="utf-8")
        print("---", name, "len", len(html))
        for n in [
            "Результат не найден",
            "результаты не найдены",
            "Аметист",
            "Роксана",
            "Алигайдеровна",
            "503225242801",
            "Follow",
        ]:
            print(" ", n, n in text)
        # result table rows
        m = re.search(r'id="ResList1"[\s\S]{0,2500}', html)
        if m:
            print(" ResList", strip(m.group(0))[:400])


if __name__ == "__main__":
    main()
