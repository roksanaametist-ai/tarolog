# Restore production jelly landing. Do not touch oferta/SiteApp.
from pathlib import Path
import re
import shutil

ROOT = Path("/root/tarolog/landing")
SRC = Path("/tmp/restore_tgz/tarolog/landing")
idx = ROOT / "templates/index.html"
css = ROOT / "static/css/main.css"

shutil.copy(idx, ROOT / "templates/index.html.bak-broken-cosmos")
shutil.copy(css, ROOT / "static/css/main.css.bak-broken-cosmos")
shutil.copy(SRC / "templates/index.html", idx)
shutil.copy(SRC / "static/css/main.css", css)

t = idx.read_text(encoding="utf-8")

card_111 = re.compile(
    r"\s*<article class=\"price-card\">\s*"
    r"<p class=\"price-card__tag\">03 · без вашего участия</p>.*?"
    r"</article>\s*",
    re.S,
)
t, n111 = card_111.subn("\n", t, count=1)
t = t.replace("Три формата работы со мной.", "Два формата работы со мной.")

CARD3333 = """                    <article class="price-card">
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
if "3 333" not in t and ANCHOR in t:
    t = t.replace(ANCHOR, CARD3333 + """                    <article class="price-card price-card--accent">
                        <p class="price-card__tag">03 · консультация</p>
""", 1)
    t = t.replace("Два формата работы со мной.", "Три формата работы со мной.")

FOOT_JELLY = """                <p class="jelly-foot__legal">© {{ year }} {{ operator_name }} · самозанятая (НПД) · ИНН {{ operator_inn }}</p>
                <p class="jelly-foot__legal">{{ operator_phone }} · {{ operator_email }}</p>
                <p class="jelly-foot__legal"><a href="{{ privacy_url }}">Политика ПД</a> · <a href="{{ oferta_url }}">Оферта</a></p>
                <p class="jelly-foot__legal">Консультация, не медицина и не гарантия событий в жизни.</p>
                <p class="site-foot-seo">Консультация эзотерика онлайн · расклад Таро · астрология · Human Design · йога · followthefrensy.ru</p>"""

FOOT_JELLY_NEW = """                <p class="site-foot-quiet">© {{ year }} {{ operator_name }} · самозанятая (НПД) · ИНН {{ operator_inn }} · <a href="{{ privacy_url }}">ПД</a> · <a href="{{ oferta_url }}">оферта</a></p>
                <p class="jelly-foot__legal">{% if operator_email %}<a href="mailto:{{ operator_email }}">{{ operator_email }}</a>{% endif %} · <a href="{{ contact_bot_url }}">Telegram</a></p>
                <p class="site-foot-seo">Консультация эзотерика онлайн · расклад Таро · астрология · Human Design · йога · followthefrensy.ru</p>"""

if FOOT_JELLY in t:
    t = t.replace(FOOT_JELLY, FOOT_JELLY_NEW)

t = t.replace("css/main.css') }}?v=142", "css/main.css') }}?v=201")
t = t.replace("css/main.css') }}?v=143", "css/main.css') }}?v=201")
t = re.sub(r"main\.css\?v=\d+", "main.css?v=201", t, count=1)
idx.write_text(t, encoding="utf-8")

css_t = css.read_text(encoding="utf-8")
extra = """
.site-foot-quiet {
  margin: 0.35rem 0 0;
  font-size: 11px;
  line-height: 1.35;
  letter-spacing: 0.01em;
  opacity: 0.55;
  color: inherit;
}
.site-foot-quiet a { color: inherit; }
"""
if ".site-foot-quiet" not in css_t:
    css.write_text(css_t + extra, encoding="utf-8")

print(
    "ok",
    "idx",
    idx.stat().st_size,
    "css",
    css.stat().st_size,
    "n111",
    n111,
    "3333",
    t.count("3 333"),
    "cards",
    t.count("price-card"),
    "jelly",
    "jelly" in t,
    "v201",
    "v=201" in t,
)
