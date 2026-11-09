# Add Robokassa + RKN links/blocks to the live jelly index without replacing the design.
from pathlib import Path
import re

ROOT = Path("/root/tarolog/landing")
idx = ROOT / "templates/index.html"
css = ROOT / "static/css/main.css"
t = idx.read_text(encoding="utf-8")
if 'id="buyer"' in t and "privacy_url" in t:
    print("already patched")
else:
    BUYER = r'''
            {% if show_lead_form %}
            {% include "_lead_form.html" %}
            {% endif %}

            <section
                class="contacts buyer-legal{% if jelly_hero %} jelly-stage jelly-stage--copy-right{% endif %}"
                id="buyer"
                aria-labelledby="buyer-title"
                {% if jelly_hero %}data-jelly-stage data-jx="-2.2" data-jy="0.2" data-jz="-0.7" data-js="0.7" data-jry="0.4" data-jkind="gem"{% endif %}
            >
                <div class="{% if jelly_hero %}jelly-stage__copy{% endif %}">
                <h2 id="buyer-title" class="contacts-title">Для покупателя</h2>
                <p class="contacts-lead">Реквизиты, оплата, сроки, возврат и обработка персональных данных — как требуют платёжный сервис и 152-ФЗ.</p>
                <ul class="buyer-list">
                    <li><strong>Реквизиты.</strong> Самозанятая {{ operator_name }}, ИНН {{ operator_inn }}, {{ operator_city }}.</li>
                    <li><strong>Контакты.</strong> Telegram: <a href="{{ consultation_url }}" target="_blank" rel="noopener">написать Роксане</a> · <a href="{{ bot_url }}" target="_blank" rel="noopener">бот</a>{% if operator_email %} · почта <a href="mailto:{{ operator_email }}">{{ operator_email }}</a>{% endif %}.</li>
                    <li><strong>Заказ и сроки.</strong> Заявка на сайте или в боте → оплата → доступ к боту обычно сразу (не позднее 24 часов). Консультация — в согласованный слот (1–14 дней). Видео в TikTok — до 14 дней.</li>
                    <li><strong>Цены.</strong> Разбор вопроса — 1 111 ₽. Видеоразбор в TikTok — 3 333 ₽. Развёрнутая консультация — 11 111 ₽. Пакеты бота — в интерфейсе бота.</li>
                    <li><strong>Оплата.</strong> Банковские карты и другие способы в форме Robokassa либо перевод по реквизитам в переписке. Чек — в «Мой налог».</li>
                    <li><strong>Оказание услуг.</strong> Цифровой доступ и консультации онлайн. Физический товар и доставка не предусмотрены.</li>
                    <li><strong>Возврат.</strong> До начала услуги — полный возврат. В процессе — за вычетом фактически оказанного. Комиссию платёжного сервиса с покупателя не удерживаем. Пишите в Telegram или на почту «Возврат»: ответ до 10 дней, деньги тем же способом. Подробности — в <a href="{{ oferta_url }}">оферте</a>.</li>
                    <li><strong>Персональные данные.</strong> <a href="{{ privacy_url }}">Политика обработки персональных данных</a> (в том числе трансграничная передача). Публичная <a href="{{ oferta_url }}">оферта</a>.</li>
                </ul>
                </div>
            </section>
'''
    cpos = t.find('id="contacts"')
    if cpos < 0:
        raise SystemExit("contacts not found")
    mpos = t.find("        </main>", cpos)
    if mpos < 0:
        raise SystemExit("main close after contacts not found")
    t = t[:mpos] + BUYER + t[mpos:]

    NAV_ADD = (
        '                        <a href="#buyer">Покупателю</a>\n'
        '                        <a href="{{ privacy_url }}">Политика ПД</a>\n'
        '                        <a href="{{ oferta_url }}">Оферта</a>\n'
    )
    nav_end = '                        <a href="#contacts">Контакты</a>\n                    </nav>'
    if nav_end in t:
        t = t.replace(
            nav_end,
            '                        <a href="#contacts">Контакты</a>\n' + NAV_ADD + "                    </nav>",
            1,
        )
    plain_nav = '                <a href="#contacts">Контакты</a>\n            </nav>'
    if plain_nav in t:
        t = t.replace(
            plain_nav,
            '                <a href="#contacts">Контакты</a>\n'
            '                <a href="#buyer">Покупателю</a>\n'
            '                <a href="{{ privacy_url }}">Политика ПД</a>\n'
            '                <a href="{{ oferta_url }}">Оферта</a>\n'
            "            </nav>",
            1,
        )

    OLD_JELLY_COPY = (
        '                <p class="jelly-foot__legal">© {{ year }} Роксана Аметист · Follow the Frensy</p>'
    )
    NEW_JELLY_COPY = (
        '                <p class="jelly-foot__legal">Самозанятая {{ operator_name }} · ИНН {{ operator_inn }} · {{ operator_city }}</p>\n'
        '                <p class="jelly-foot__legal">{% if operator_email %}<a href="mailto:{{ operator_email }}">{{ operator_email }}</a> · {% endif %}<a href="{{ privacy_url }}">Политика ПД</a> · <a href="{{ oferta_url }}">Оферта</a></p>'
    )
    if OLD_JELLY_COPY not in t:
        raise SystemExit("jelly copyright not found")
    t = t.replace(OLD_JELLY_COPY, NEW_JELLY_COPY, 1)

    OLD_PLAIN_COPY = '            <p>© {{ year }} Роксана Аметист · Follow the Frensy</p>'
    NEW_PLAIN_COPY = (
        '            <p>Самозанятая {{ operator_name }} · ИНН {{ operator_inn }} · {{ operator_city }}</p>\n'
        '            <p>{% if operator_email %}<a href="mailto:{{ operator_email }}">{{ operator_email }}</a> · {% endif %}<a href="{{ privacy_url }}">Политика ПД</a> · <a href="{{ oferta_url }}">Оферта</a></p>'
    )
    if OLD_PLAIN_COPY in t:
        t = t.replace(OLD_PLAIN_COPY, NEW_PLAIN_COPY, 1)

    t = re.sub(r"main\.css\?v=\d+", "main.css?v=202", t, count=1)
    idx.write_text(t, encoding="utf-8")
    print("index patched", idx.stat().st_size)

css_t = css.read_text(encoding="utf-8")
EXTRA = """
.buyer-list {
  margin: 0.8rem 0 0;
  padding-left: 1.1rem;
  max-width: 42rem;
  line-height: 1.45;
}
.buyer-list li { margin: 0.45rem 0; }
.buyer-list a { color: inherit; text-decoration: underline; }
.jelly-foot__legal a, .site-foot a[href*="privacy"], .site-foot a[href*="oferta"] {
  color: inherit;
}
"""
if ".buyer-list" not in css_t:
    css.write_text(css_t + EXTRA, encoding="utf-8")
    print("css appended", css.stat().st_size)
else:
    print("css already has buyer-list")
