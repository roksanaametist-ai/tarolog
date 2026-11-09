# -*- coding: utf-8 -*-
from pathlib import Path
import sys

CARD = """                    <article class="price-card">
                        <p class="price-card__tag">02 · TikTok</p>
                        <h3 class="price-card__name">Видеоразбор</h3>
                        <p class="price-card__sum">3 333 ₽</p>
                        <p class="price-card__note">Публичный ролик в TikTok по вашему вопросу. Код заказа — в комментарии. Личных уведомлений нет: ролик ищите в течение 14 дней.</p>
                        <a href="{{ consultation_url }}" target="_blank" rel="noopener" class="price-card__link">Написать Роксане</a>
                    </article>
"""

ANCHOR = """                    <article class="price-card price-card--accent">
                        <p class="price-card__tag">02 · консультация</p>
"""

ANCHOR_NEW = CARD + """                    <article class="price-card price-card--accent">
                        <p class="price-card__tag">03 · консультация</p>
"""

FAQ_OLD_1 = '            "Форматы: один расклад 1 111 ₽, полная консультация 11 111 ₽."'
FAQ_NEW_1 = (
    '            "Форматы: один расклад 1 111 ₽, видеоразбор в TikTok 3 333 ₽, '
    'полная консультация 11 111 ₽."'
)
FAQ_OLD_2 = (
    '            "Один расклад на ваш вопрос — 1 111 ₽, каждый следующий вопрос столько же. "\n'
    '            "Полная консультация до разрешения запроса — 11 111 ₽."'
)
FAQ_NEW_2 = (
    '            "Один расклад на ваш вопрос — 1 111 ₽, каждый следующий вопрос столько же. "\n'
    '            "Видеоразбор в TikTok — 3 333 ₽. Полная консультация до разрешения запроса — 11 111 ₽."'
)

JSON_OLD = '''                        {
                            "@type": "Offer",
                            "@id": f"{consult_offer_id}-full",
                            "name": "Полноценная консультация эзотерика онлайн",
                            "url": CONSULTATION_URL,
                            "price": "11111",
'''

JSON_NEW = '''                        {
                            "@type": "Offer",
                            "@id": f"{consult_offer_id}-tiktok",
                            "name": "Видеоразбор в TikTok",
                            "url": CONSULTATION_URL,
                            "price": "3333",
                            "priceCurrency": "RUB",
                            "availability": "https://schema.org/InStock",
                            "category": "Расклад Таро",
                        },
                        {
                            "@type": "Offer",
                            "@id": f"{consult_offer_id}-full",
                            "name": "Полноценная консультация эзотерика онлайн",
                            "url": CONSULTATION_URL,
                            "price": "11111",
'''

OFERTA_OLD = (
    "    <li>один разбор вопроса — 1 111 ₽; каждый следующий отдельный вопрос в том же формате — ещё 1 111 ₽;</li>\n"
    "    <li>развёрнутая консультация по запросу — 11 111 ₽.</li>\n"
)
OFERTA_NEW = (
    "    <li>один разбор вопроса — 1 111 ₽; каждый следующий отдельный вопрос в том же формате — ещё 1 111 ₽;</li>\n"
    "    <li>видеоразбор в TikTok — 3 333 ₽: публичный ролик по коду заказа, без личного уведомления, срок размещения — 14 дней;</li>\n"
    "    <li>развёрнутая консультация по запросу — 11 111 ₽.</li>\n"
)


def patch_root(root: Path) -> None:
    idx = root / "templates" / "index.html"
    t = idx.read_text(encoding="utf-8")
    if "3 333" in t:
        print(root, "index already has 3333")
    else:
        if ANCHOR not in t:
            raise SystemExit(f"price anchor not found in {idx}")
        t = t.replace(ANCHOR, ANCHOR_NEW, 1)
        t = t.replace("Два формата работы со мной.", "Три формата работы со мной.")
        t = t.replace("main.css') }}?v=143", "main.css') }}?v=145")
        t = t.replace("main.css?v=143", "main.css?v=145")
        idx.write_text(t, encoding="utf-8")

    app = root / "SiteApp.py"
    a = app.read_text(encoding="utf-8")
    if '"3333"' not in a:
        if FAQ_OLD_1 not in a:
            raise SystemExit("faq1 not found")
        if FAQ_OLD_2 not in a:
            raise SystemExit("faq2 not found")
        if JSON_OLD not in a:
            raise SystemExit("json not found")
        a = a.replace(FAQ_OLD_1, FAQ_NEW_1).replace(FAQ_OLD_2, FAQ_NEW_2).replace(JSON_OLD, JSON_NEW)
        app.write_text(a, encoding="utf-8")

    of = root / "templates" / "oferta.html"
    o = of.read_text(encoding="utf-8")
    if "3 333" not in o:
        if OFERTA_OLD not in o:
            raise SystemExit("oferta list not found")
        of.write_text(o.replace(OFERTA_OLD, OFERTA_NEW), encoding="utf-8")

    lp = root / "legal_pages.py"
    if lp.exists():
        s = lp.read_text(encoding="utf-8")
        lp.write_text(s.replace('OFERTA_EDITION = "16.10.2026"', 'OFERTA_EDITION = "17.10.2026"'), encoding="utf-8")

    print(
        root,
        "idx3333",
        (root / "templates/index.html").read_text(encoding="utf-8").count("3 333"),
        "app3333",
        (root / "SiteApp.py").read_text(encoding="utf-8").count("3 333"),
        "of3333",
        (root / "templates/oferta.html").read_text(encoding="utf-8").count("3 333"),
    )


if __name__ == "__main__":
    patch_root(Path(sys.argv[1]))
