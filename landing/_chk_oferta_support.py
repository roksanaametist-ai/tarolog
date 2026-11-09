import urllib.request

html = urllib.request.urlopen("https://followthefrensy.ru/oferta", timeout=20).read().decode(
    "utf-8", "replace"
)
keys = [
    "26.10.2026",
    "Добровольная поддержка проекта",
    "Автору контента",
    "чаевые автору",
    "встречных обязательств",
    "пожертвование благотворительному фонду",
]
print({k: k in html for k in keys})
