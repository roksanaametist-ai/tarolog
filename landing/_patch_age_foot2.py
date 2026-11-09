from pathlib import Path
import os

p = Path(os.environ.get("LEGAL_LANDING_ROOT", "/opt/targpt/landing")) / "templates" / "index.html"
t = p.read_text(encoding="utf-8")
old = """            <p class="site-foot-legal">Самозанятая {{ operator_name }} · ИНН {{ operator_inn }} · {{ operator_city }}</p>
            <p class="site-foot-legal">
                <a href="{{ bot_url }}" target="_blank" rel="noopener">Telegram</a>
                {% if operator_email %} · <a href="mailto:{{ operator_email }}">{{ operator_email }}</a>{% endif %}
                · <a href="{{ privacy_url }}">Политика ПД</a>
                · <a href="{{ oferta_url }}">Оферта</a>
            </p>"""
new = """            <p class="site-foot-legal">Самозанятая {{ operator_name }} · ИНН {{ operator_inn }} · {{ operator_city }}</p>
            <p class="site-foot-legal">Сайт и услуги для лиц старше 18 лет. Консультация, не медицина и не гарантия событий в жизни.</p>
            <p class="site-foot-legal">
                <a href="{{ bot_url }}" target="_blank" rel="noopener">Telegram</a>
                {% if operator_email %} · <a href="mailto:{{ operator_email }}">{{ operator_email }}</a>{% endif %}
                · <a href="{{ privacy_url }}">Политика ПД</a>
                · <a href="{{ oferta_url }}">Оферта</a>
            </p>"""
if "старше 18 лет" in t:
    print("skip already")
elif old in t:
    p.write_text(t.replace(old, new, 1), encoding="utf-8")
    print("ok cosmos-foot")
else:
    print("missing")
print("count18", p.read_text(encoding="utf-8").count("старше 18 лет"))
print("fonts.css", "fonts.css" in p.read_text(encoding="utf-8"))
print("googleapis_link", "fonts.googleapis.com/css2" in p.read_text(encoding="utf-8"))
