from pathlib import Path

FOOT_JELLY = """                <p class="jelly-foot__legal">© {{ year }} {{ operator_name }} · самозанятая (НПД) · ИНН {{ operator_inn }}</p>
                <p class="jelly-foot__legal">{{ operator_phone }} · {{ operator_email }}</p>
                <p class="jelly-foot__legal"><a href="{{ privacy_url }}">Политика ПД</a> · <a href="{{ oferta_url }}">Оферта</a></p>
                <p class="jelly-foot__legal">Консультация, не медицина и не гарантия событий в жизни.</p>
                <p class="site-foot-seo">Консультация эзотерика онлайн · расклад Таро · астрология · Human Design · йога · followthefrensy.ru</p>"""

FOOT_JELLY_NEW = """                <p class="site-foot-quiet">© {{ year }} {{ operator_name }} · НПД · ИНН {{ operator_inn }} · <a href="{{ privacy_url }}">ПД</a> · <a href="{{ oferta_url }}">оферта</a></p>
                <p class="site-foot-seo">Консультация эзотерика онлайн · расклад Таро · астрология · Human Design · йога · followthefrensy.ru</p>"""

FOOT_PLAIN = """            <p>© {{ year }} {{ operator_name }} · самозанятая (НПД) · ИНН {{ operator_inn }}</p>
            <p>{{ operator_phone }} · {{ operator_email }}</p>
            <p><a href="{{ privacy_url }}">Политика ПД</a> · <a href="{{ oferta_url }}">Оферта</a></p>
            <p>Консультация, не медицина и не гарантия событий в жизни.</p>
            <p class="site-foot-seo">Консультация эзотерика онлайн · расклад Таро · астрология · Human Design · йога · followthefrensy.ru</p>"""

FOOT_PLAIN_NEW = """            <p class="site-foot-quiet">© {{ year }} {{ operator_name }} · НПД · ИНН {{ operator_inn }} · <a href="{{ privacy_url }}">ПД</a> · <a href="{{ oferta_url }}">оферта</a></p>
            <p class="site-foot-seo">Консультация эзотерика онлайн · расклад Таро · астрология · Human Design · йога · followthefrensy.ru</p>"""

PRICE_OLD = "Это не плата «за событие в жизни» и не гарантия результата."
PRICE_NEW = "Дальнейшая работа и расчёты — только по отдельному согласованию объёма."

CSS = """
.site-foot-quiet {
  margin: 0.35rem 0 0;
  font-size: 11px;
  line-height: 1.35;
  letter-spacing: 0.01em;
  opacity: 0.38;
  color: inherit;
}
.site-foot-quiet a {
  color: inherit;
  text-decoration: none;
  border-bottom: 1px solid currentColor;
  opacity: 0.9;
}
.jelly-foot .site-foot-quiet {
  font-size: 10px;
  opacity: 0.32;
}
"""


def patch_index(p: Path) -> None:
    t = p.read_text(encoding="utf-8")
    n = 0
    if FOOT_JELLY in t:
        t = t.replace(FOOT_JELLY, FOOT_JELLY_NEW)
        n += 1
    if FOOT_PLAIN in t:
        t = t.replace(FOOT_PLAIN, FOOT_PLAIN_NEW)
        n += 1
    t2 = t.replace(PRICE_OLD, PRICE_NEW)
    t2 = t2.replace("гарантия результата", "гарантия исхода")
    t2 = t2.replace("при результате", "по согласованию")
    t2 = t2.replace("ждёте результат", "идёт работа по запросу")
    t2 = t2.replace("При получении результата", "Если стороны согласовали продолжение")
    p.write_text(t2, encoding="utf-8")
    print("index", p, "foot_blocks", n)


def patch_css(p: Path) -> None:
    t = p.read_text(encoding="utf-8")
    if ".site-foot-quiet" in t:
        print("css already", p)
        return
    p.write_text(t + CSS, encoding="utf-8")
    print("css", p)


def patch_py(p: Path) -> None:
    t = p.read_text(encoding="utf-8")
    t2 = (
        t.replace("при результате", "по согласованию")
        .replace("гарантия результата", "гарантия исхода")
        .replace("доплата 100 000 ₽ при результате", "дальнейшие расчёты по согласованному объёму")
    )
    if t2 != t:
        p.write_text(t2, encoding="utf-8")
        print("py changed", p)
    else:
        print("py unchanged", p)


if __name__ == "__main__":
    import sys

    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
    patch_index(root / "templates" / "index.html")
    patch_css(root / "static" / "css" / "main.css")
    patch_py(root / "SiteApp.py")
