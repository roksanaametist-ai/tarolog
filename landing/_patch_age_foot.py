from pathlib import Path
import os

p = Path(os.environ.get("LEGAL_LANDING_ROOT", "/root/tarolog/landing")) / "templates" / "index.html"
t = p.read_text(encoding="utf-8")
old = (
    "            <p>Самозанятая {{ operator_name }} · ИНН {{ operator_inn }} · {{ operator_city }}</p>\n"
    "            <p>{% if operator_email %}<a href=\"mailto:{{ operator_email }}\">{{ operator_email }}</a> · {% endif %}"
    "<a href=\"{{ privacy_url }}\">Политика ПД</a> · <a href=\"{{ oferta_url }}\">Оферта</a></p>"
)
new = (
    "            <p>Самозанятая {{ operator_name }} · ИНН {{ operator_inn }} · {{ operator_city }}</p>\n"
    "            <p>Сайт и услуги для лиц старше 18 лет. Консультация, не медицина и не гарантия событий в жизни.</p>\n"
    "            <p>{% if operator_email %}<a href=\"mailto:{{ operator_email }}\">{{ operator_email }}</a> · {% endif %}"
    "<a href=\"{{ privacy_url }}\">Политика ПД</a> · <a href=\"{{ oferta_url }}\">Оферта</a></p>"
)
if old in t:
    p.write_text(t.replace(old, new, 1), encoding="utf-8")
    print("ok else-foot")
else:
    print("skip-or-missing")
    i = t.find("Самозанятая {{ operator_name }}")
    print(repr(t[i : i + 450]))
print("count18", p.read_text(encoding="utf-8").count("старше 18 лет"))
