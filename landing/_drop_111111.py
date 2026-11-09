# -*- coding: utf-8 -*-
from pathlib import Path
import re

CARD = re.compile(
    r"\s*<article class=\"price-card\">\s*"
    r"<p class=\"price-card__tag\">03 · без вашего участия</p>.*?"
    r"</article>\s*",
    re.S,
)

FAQ_OLD_1 = (
    '            "Форматы: один расклад 1 111 ₽, полная консультация 11 111 ₽, "\n'
    '            "решение вопроса без вашего участия 111 111 ₽."'
)
FAQ_NEW_1 = (
    '            "Форматы: один расклад 1 111 ₽, полная консультация 11 111 ₽."'
)
FAQ_OLD_2 = (
    '            "Полная консультация до разрешения запроса — 11 111 ₽. "\n'
    '            "Расширенное сопровождение — 111 111 ₽: предоплата 11 111 ₽ за консультацию; дальнейшие расчёты только по согласованному объёму работы, без гарантии событий в жизни."'
)
FAQ_NEW_2 = '            "Полная консультация до разрешения запроса — 11 111 ₽."'

JSON_OLD = '''                        {
                            "@type": "Offer",
                            "@id": f"{consult_offer_id}-result",
                            "name": "Решение вопроса без участия клиента",
                            "url": CONSULTATION_URL,
                            "price": "111111",
                            "priceCurrency": "RUB",
                            "availability": "https://schema.org/InStock",
                            "category": "Консультация эзотерика онлайн",
                        },
'''

OFERTA_OLD = (
    "    <li>развёрнутая консультация по запросу — 11 111 ₽;</li>\n"
    "    <li>расширенное сопровождение — 111 111 ₽: предоплата 11 111 ₽ за консультацию; "
    "дальнейшая работа и расчёты только если стороны явно согласовали объём. "
    "Доплата не создаёт обязанности Исполнителя добиться внешнего события.</li>\n"
)
OFERTA_NEW = "    <li>развёрнутая консультация по запросу — 11 111 ₽.</li>\n"


def patch_root(root: Path) -> None:
    idx = root / "templates" / "index.html"
    t = idx.read_text(encoding="utf-8")
    n = len(CARD.findall(t))
    t2 = CARD.sub("\n", t, count=1)
    t2 = t2.replace("Три формата работы со мной.", "Два формата работы со мной.")
    idx.write_text(t2, encoding="utf-8")

    app = root / "SiteApp.py"
    a = app.read_text(encoding="utf-8")
    c1 = a.count("111 111") + a.count('"111111"')
    a2 = a.replace(FAQ_OLD_1, FAQ_NEW_1).replace(FAQ_OLD_2, FAQ_NEW_2).replace(JSON_OLD, "")
    app.write_text(a2, encoding="utf-8")

    of = root / "templates" / "oferta.html"
    o = of.read_text(encoding="utf-8")
    c2 = o.count("111 111")
    of.write_text(o.replace(OFERTA_OLD, OFERTA_NEW), encoding="utf-8")

    css = root / "templates" / "index.html"
    html = css.read_text(encoding="utf-8")
    html2, nb = re.subn(r"main\.css\?v=\d+", "main.css?v=144", html, count=1)
    if nb:
        css.write_text(html2, encoding="utf-8")

    print(
        root,
        "cards",
        n,
        "faq_left",
        a2.count("111 111") + a2.count('"111111"'),
        "oferta_left",
        of.read_text(encoding="utf-8").count("111 111"),
        "idx_left",
        idx.read_text(encoding="utf-8").count("111 111"),
        "css_bump",
        nb,
        "was_faq",
        c1,
        "was_of",
        c2,
    )


if __name__ == "__main__":
    import sys

    patch_root(Path(sys.argv[1]))
