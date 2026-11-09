import urllib.request

html = urllib.request.urlopen("https://followthefrensy.ru/", timeout=20).read().decode("utf-8", "replace")
print("buyer heading", "Для покупателя" in html)
print("buyer id", 'id="buyer"' in html)
print("privacy", "/privacy" in html)
print("oferta", "/oferta" in html)
print("inn", "503225242801" in html)
print("patronymic", "Алигайдеровна" in html)
print("shell", "shell-cycle" in html)
print("css", [line.strip() for line in html.splitlines() if "main.css" in line][:2])
