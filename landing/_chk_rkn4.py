import ssl
import urllib.parse
import urllib.request
from pathlib import Path

CTX = ssl.create_default_context()
UA = {"User-Agent": "Mozilla/5.0"}
q = urllib.parse.urlencode({"act": "search", "name_full": "Яндекс", "inn": "7736207543", "regn": ""})
url = "https://pd.rkn.gov.ru/operators-registry/operators-list/?" + q
req = urllib.request.Request(url, headers=UA)
with urllib.request.urlopen(req, timeout=40, context=CTX) as r:
    html = r.read().decode("utf-8", "replace")
print("yandex notfound", "Записей не найдено" in html)
print("yandex name", "Яндекс" in html)
print("yandex inn", "7736207543" in html)
Path(r"C:\Users\roxan\Projects\TarGPT3\landing\_rkn_out\yandex.html").write_text(html, encoding="utf-8")
