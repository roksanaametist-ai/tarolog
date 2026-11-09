# python3 landing/_apply_legal_prod.py
import os
from pathlib import Path

ROOT = Path(os.environ.get("LEGAL_LANDING_ROOT", "/opt/targpt/landing"))
site = ROOT / "SiteApp.py"
lead = ROOT / "templates" / "_lead_form.html"
index = ROOT / "templates" / "index.html"
js = ROOT / "static" / "js" / "lead-form.js"
css = ROOT / "static" / "css" / "main.css"
bot = Path(os.environ.get("LEGAL_BOT_MAIN", "/opt/targpt/main.py"))
SKIP_BOT = os.environ.get("LEGAL_SKIP_BOT") == "1"


def once(path: Path, old: str, new: str, label: str) -> None:
    text = path.read_text(encoding="utf-8")
    if new.strip() and new in text and old not in text:
        print("skip", label)
        return
    if old not in text:
        raise SystemExit(f"missing {label} in {path}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    print("ok", label)


t = site.read_text(encoding="utf-8")
if "from legal_pages import register_legal" not in t:
    t = t.replace(
        "from flask import Flask, Response, abort, jsonify, redirect, render_template, request, send_from_directory\n",
        "from flask import Flask, Response, abort, jsonify, redirect, render_template, request, send_from_directory\n"
        "from legal_pages import register_legal\n",
        1,
    )
if "register_legal(app)" not in t:
    t = t.replace("app = Flask(__name__)\n", "app = Flask(__name__)\nregister_legal(app)\n", 1)

old_consent = """    consent = payload.get("consent") in (True, 1, "1", "true", "yes", "on")

    if not name or len(name) < 2:
        return jsonify({"ok": False, "error": "Укажите имя"}), 400
    if not contact or len(contact) < 3:
        return jsonify({"ok": False, "error": "Укажите Telegram, WhatsApp или телефон"}), 400
    if not consent:
        return jsonify({"ok": False, "error": "Нужно согласие на связь"}), 400
"""
new_consent = """    consent = payload.get("consent") in (True, 1, "1", "true", "yes", "on")
    consent_pd = payload.get("consent_pd") in (True, 1, "1", "true", "yes", "on") or consent
    consent_oferta = payload.get("consent_oferta") in (True, 1, "1", "true", "yes", "on")

    if not name or len(name) < 2:
        return jsonify({"ok": False, "error": "Укажите имя"}), 400
    if not contact or len(contact) < 3:
        return jsonify({"ok": False, "error": "Укажите Telegram, WhatsApp или телефон"}), 400
    if not consent_pd:
        return jsonify({"ok": False, "error": "Нужно согласие на обработку персональных данных"}), 400
    if not consent_oferta:
        return jsonify({"ok": False, "error": "Нужно принять оферту"}), 400
"""
if old_consent in t:
    t = t.replace(old_consent, new_consent, 1)
    print("ok siteapi")
elif "consent_oferta" in t:
    print("skip siteapi")
else:
    raise SystemExit("lead api anchor missing")

t = t.replace('"consent": True,', '"consent": True,\n        "consent_pd": True,\n        "consent_oferta": True,', 1)

old_map = """    for i, raw in enumerate(reading_urls):"""
new_map = """    for extra_path, pri in (("/privacy", "0.4"), ("/oferta", "0.4")):
        loc = xml_escape(f"{SITE_URL}{extra_path}")
        url_blocks.append(
            f\"\"\"  <url>
    <loc>{loc}</loc>
    <lastmod>{lastmod}</lastmod>
    <changefreq>monthly</changefreq>
    <priority>{pri}</priority>
  </url>\"\"\"
        )
    for i, raw in enumerate(reading_urls):"""
if "/privacy" not in t or '("/privacy", "0.4")' not in t:
    if old_map not in t:
        raise SystemExit("sitemap anchor missing")
    t = t.replace(old_map, new_map, 1)
    print("ok sitemap")
else:
    print("skip sitemap")

site.write_text(t, encoding="utf-8")

lead_old = """        <label class="lead-check">
            <input type="checkbox" name="consent" value="1" required>
            <span>Согласен(на), чтобы мне написали по этому контакту по поводу консультации</span>
        </label>"""
lead_new = """        <label class="lead-check">
            <input type="checkbox" name="consent_pd" value="1" required>
            <span>Согласен(на) на обработку персональных данных по <a href="{{ privacy_url }}" target="_blank" rel="noopener">политике</a></span>
        </label>
        <label class="lead-check">
            <input type="checkbox" name="consent_oferta" value="1" required>
            <span>Принимаю <a href="{{ oferta_url }}" target="_blank" rel="noopener">оферту</a>, мне есть 18 лет. Услуга консультационная: не медицина и не гарантия событий в жизни.</span>
        </label>"""
once(lead, lead_old, lead_new, "lead_form")

idx = index.read_text(encoding="utf-8")
foot_old = """                <p class="jelly-foot__legal">© {{ year }} Роксана Аметист · Follow the Frensy</p>
                <p class="site-foot-seo">Консультация эзотерика онлайн · расклад Таро · астрология · Human Design · йога · followthefrensy.ru</p>"""
foot_new = """                <p class="jelly-foot__legal">© {{ year }} {{ operator_name }} · самозанятая (НПД) · ИНН {{ operator_inn }}</p>
                <p class="jelly-foot__legal">{{ operator_phone }} · {{ operator_email }}</p>
                <p class="jelly-foot__legal"><a href="{{ privacy_url }}">Политика ПД</a> · <a href="{{ oferta_url }}">Оферта</a></p>
                <p class="jelly-foot__legal">Консультация, не медицина и не гарантия событий в жизни.</p>
                <p class="site-foot-seo">Консультация эзотерика онлайн · расклад Таро · астрология · Human Design · йога · followthefrensy.ru</p>"""
if foot_old in idx:
    idx = idx.replace(foot_old, foot_new, 1)
    print("ok jelly foot")
else:
    print("skip jelly foot")

plain_old = """            <p>© {{ year }} Роксана Аметист · Follow the Frensy</p>
            <p class="site-foot-seo">Консультация эзотерика онлайн · расклад Таро · астрология · Human Design · йога · followthefrensy.ru</p>"""
plain_new = """            <p>© {{ year }} {{ operator_name }} · самозанятая (НПД) · ИНН {{ operator_inn }}</p>
            <p>{{ operator_phone }} · {{ operator_email }}</p>
            <p><a href="{{ privacy_url }}">Политика ПД</a> · <a href="{{ oferta_url }}">Оферта</a></p>
            <p>Консультация, не медицина и не гарантия событий в жизни.</p>
            <p class="site-foot-seo">Консультация эзотерика онлайн · расклад Таро · астрология · Human Design · йога · followthefrensy.ru</p>"""
if plain_old in idx:
    idx = idx.replace(plain_old, plain_new, 1)
    print("ok plain foot")
else:
    print("skip plain foot")

price_old = """                        <p class="price-card__note">Говорите, что нужно. Предоплата как за консультацию — 11 111 ₽. После консультации ждёте результат. При получении результата — доплата 100 000 ₽.</p>"""
price_new = """                        <p class="price-card__note">Предоплата 11 111 ₽ за консультацию. Дальнейшая работа и расчёты — только по отдельному согласованию объёма. Это не плата «за событие в жизни» и не гарантия результата.</p>"""
if price_old in idx:
    idx = idx.replace(price_old, price_new, 1)
    print("ok price")
else:
    print("skip price")

if "lead-form.js" not in idx:
    idx = idx.replace(
        '<script src="{{ url_for(\'static\', filename=\'js/main.js\') }}?v=103" defer></script>',
        '<script src="{{ url_for(\'static\', filename=\'js/lead-form.js\') }}?v=2" defer></script>\n    <script src="{{ url_for(\'static\', filename=\'js/main.js\') }}?v=103" defer></script>',
        1,
    )
    print("ok lead js include")
index.write_text(idx, encoding="utf-8")

js_text = js.read_text(encoding="utf-8")
js_old = """      if (!fd.get("consent")) {
        if (status) {
          status.hidden = false;
          status.textContent = "Нужно согласие на связь.";
          status.className = "lead-status is-err";
        }
        return;
      }"""
js_new = """      if (!fd.get("consent_pd") || !fd.get("consent_oferta")) {
        if (status) {
          status.hidden = false;
          status.textContent = "Нужны согласие на обработку данных и принятие оферты.";
          status.className = "lead-status is-err";
        }
        return;
      }"""
if js_old in js_text:
    js_text = js_text.replace(js_old, js_new, 1)
    js_text = js_text.replace(
        """          consent: true,""",
        """          consent: true,
          consent_pd: true,
          consent_oferta: true,""",
        1,
    )
    js.write_text(js_text, encoding="utf-8")
    print("ok js")
else:
    print("skip js")

css_text = css.read_text(encoding="utf-8")
addon = """
.jelly-foot__legal a, .site-foot a { color: inherit; text-decoration: underline; }
.lead-check a { color: inherit; }
"""
if ".jelly-foot__legal a" not in css_text:
    css.write_text(css_text + addon, encoding="utf-8")
    print("ok css")

if SKIP_BOT:
    print("skip bot")
    raise SystemExit(0)

# --- bot ---
b = bot.read_text(encoding="utf-8")
b = b.replace(
    'AGREEMENT_URL = "https://telegra.ph/Polzovatelskoe-soglashenie-01-21-11"\n',
    'AGREEMENT_URL = "https://followthefrensy.ru/oferta"\n'
    'PRIVACY_URL = os.getenv("PRIVACY_URL", "https://followthefrensy.ru/privacy").strip()\n'
    'OFERTA_URL = os.getenv("OFERTA_URL", "https://followthefrensy.ru/oferta").strip()\n'
    "PD_GATE_TEXT = (\n"
    '    "Чтобы пользоваться ботом, нужно отдельное согласие на обработку персональных данных.\\n\\n"\n'
    '    f"Политика: {PRIVACY_URL}\\n\\n"\n'
    '    "Нажимая кнопку, вы соглашаетесь на обработку данных для услуги "\n'
    '    "(мессенджеры, баланс, переписка; часть данных может уходить за рубеж — см. политику)."\n'
    ")\n"
    "OFERTA_GATE_TEXT = (\n"
    '    "Теперь примите публичную оферту. Это консультация / доступ к боту, "\n'
    '    "не медицина и не гарантия событий в жизни. Подтверждаете, что вам есть 18 лет.\\n\\n"\n'
    '    f"Оферта: {OFERTA_URL}"\n'
    ")\n",
    1,
)

old_has = """    def user_has_agreed(self, user_id):
        agreements = self.load_agreements()
        return str(user_id) in agreements"""
new_has = """    def user_has_agreed(self, user_id):
        return self.load_agreements().get(str(user_id)) is True

    def has_pd_consent(self, user_id):
        v = self.load_agreements().get(str(user_id))
        return v is True or v == "pd"

    def add_pd_consent(self, user_id):
        if self.user_has_agreed(user_id):
            return
        agreements = self.load_agreements()
        agreements[str(user_id)] = "pd"
        self.save_agreements(agreements)"""
if old_has in b:
    b = b.replace(old_has, new_has, 1)
    print("ok has_agreed")
else:
    print("skip has_agreed")

old_kb = """def get_agreement_keyboard(*, bonus: bool = False):
    builder = InlineKeyboardBuilder()
    if bonus:
        builder.button(
            text=f"✅ Подтвердить и получить +{AGREE_BONUS_AMOUNT}",
            callback_data="agree_bonus15",
        )
    else:
        builder.button(text="✅ Подтвердить", callback_data="agree")
    builder.button(text="❌ Отказаться", callback_data="disagree")
    return builder.as_markup()"""
new_kb = """def get_pd_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Согласен на обработку ПД", callback_data="agree_pd")
    builder.button(text="❌ Отказаться", callback_data="disagree")
    builder.adjust(1)
    return builder.as_markup()


def get_agreement_keyboard(*, bonus: bool = False):
    builder = InlineKeyboardBuilder()
    if bonus:
        builder.button(
            text=f"✅ Принимаю оферту и +{AGREE_BONUS_AMOUNT}",
            callback_data="agree_bonus15",
        )
    else:
        builder.button(text="✅ Принимаю оферту, мне 18+", callback_data="agree")
    builder.button(text="❌ Отказаться", callback_data="disagree")
    builder.adjust(1)
    return builder.as_markup()"""
if "agree_pd" not in b:
    if old_kb not in b:
        raise SystemExit("keyboard anchor missing")
    b = b.replace(old_kb, new_kb, 1)
    print("ok kb")
else:
    print("skip kb")

old_start = """        if agree15:
            await message.answer(
                "Для доступа к боту подтвердите доп. соглашение.\\n\\n"
                f"📄 {AGREEMENT_URL}\\n\\n"
                f"🎁 За подтверждение начислим +{AGREE_BONUS_AMOUNT} раскладов.",
                reply_markup=get_agreement_keyboard(bonus=True),
            )
        else:
            await message.answer(
                "Для предоставления доступа к работе с ботом вам необходимо ознакомиться с доп. соглашением.\\n\\n"
                f"Оно расположено по ссылке:\\n{AGREEMENT_URL}",
                reply_markup=get_agreement_keyboard(),
            )"""
new_start = """        if not agreement_manager.has_pd_consent(user_id):
            await message.answer(PD_GATE_TEXT, reply_markup=get_pd_keyboard())
        elif agree15:
            await message.answer(
                OFERTA_GATE_TEXT + f"\\n\\n🎁 За принятие оферты начислим +{AGREE_BONUS_AMOUNT} раскладов.",
                reply_markup=get_agreement_keyboard(bonus=True),
            )
        else:
            await message.answer(
                OFERTA_GATE_TEXT,
                reply_markup=get_agreement_keyboard(),
            )"""
# file uses real newlines not escaped - the ssh dump showed real \n in source as characters in strings
old_start_real = """        if agree15:
            await message.answer(
                "Для доступа к боту подтвердите доп. соглашение.\\n\\n"
                f"📄 {AGREEMENT_URL}\\n\\n"
                f"🎁 За подтверждение начислим +{AGREE_BONUS_AMOUNT} раскладов.",
                reply_markup=get_agreement_keyboard(bonus=True),
            )
        else:
            await message.answer(
                "Для предоставления доступа к работе с ботом вам необходимо ознакомиться с доп. соглашением.\\n\\n"
                f"Оно расположено по ссылке:\\n{AGREEMENT_URL}",
                reply_markup=get_agreement_keyboard(),
            )"""

# Read exact from disk after first replacements by searching unique snippet
if "PD_GATE_TEXT" in b and "has_pd_consent(user_id)" in b[b.find("if not agreement_manager.user_has_agreed"):b.find("if not agreement_manager.user_has_agreed")+800]:
    print("skip start already")
else:
    marker = '        if agree15:\n            await message.answer(\n                "Для доступа к боту подтвердите доп. соглашение.'
    idx = b.find(marker)
    if idx < 0:
        raise SystemExit("start marker missing")
    end = b.find("                reply_markup=get_agreement_keyboard(),\n            )", idx)
    if end < 0:
        raise SystemExit("start end missing")
    end = end + len("                reply_markup=get_agreement_keyboard(),\n            )")
    b = b[:idx] + """        if not agreement_manager.has_pd_consent(user_id):
            await message.answer(PD_GATE_TEXT, reply_markup=get_pd_keyboard())
        elif agree15:
            await message.answer(
                OFERTA_GATE_TEXT + f"\\n\\n🎁 За принятие оферты начислим +{AGREE_BONUS_AMOUNT} раскладов.",
                reply_markup=get_agreement_keyboard(bonus=True),
            )
        else:
            await message.answer(
                OFERTA_GATE_TEXT,
                reply_markup=get_agreement_keyboard(),
            )""" + b[end:]
    print("ok start")

cb_old = '@dp.callback_query(F.data.in_(["agree", "disagree", "agree_bonus15", "agree_dontsign"]))'
cb_new = '@dp.callback_query(F.data.in_(["agree", "disagree", "agree_bonus15", "agree_dontsign", "agree_pd"]))'
if cb_old in b:
    b = b.replace(cb_old, cb_new, 1)
    print("ok cb filter")

proc = '''    if callback.data in {"agree", "agree_bonus15", "agree_dontsign"}:
        agreement_manager.add_user_agreement(user_id)'''
proc_new = '''    if callback.data == "agree_pd":
        agreement_manager.add_pd_consent(user_id)
        agree15 = (
            _agree_bonus_invited(user_id)
            or _wants_dont_sign_spread(user_id)
        )
        if agree15:
            await callback.message.answer(
                OFERTA_GATE_TEXT + f"\\n\\n🎁 За принятие оферты начислим +{AGREE_BONUS_AMOUNT} раскладов.",
                reply_markup=get_agreement_keyboard(bonus=True),
            )
        else:
            await callback.message.answer(
                OFERTA_GATE_TEXT,
                reply_markup=get_agreement_keyboard(),
            )
        await callback.answer()
        return

    if callback.data in {"agree", "agree_bonus15", "agree_dontsign"}:
        if not agreement_manager.has_pd_consent(user_id):
            await callback.message.answer(PD_GATE_TEXT, reply_markup=get_pd_keyboard())
            await callback.answer()
            return
        agreement_manager.add_user_agreement(user_id)'''
if "callback.data == \"agree_pd\"" not in b:
    if proc not in b:
        raise SystemExit("process_agreement anchor missing")
    b = b.replace(proc, proc_new, 1)
    print("ok process")
else:
    print("skip process")

dont = '''        await answer(
            "Сначала подтверди соглашение — потом сразу ответ карт.",
            reply_markup=get_agreement_keyboard(bonus=True),
        )'''
dont_new = '''        if not agreement_manager.has_pd_consent(chat_id):
            await answer(PD_GATE_TEXT, reply_markup=get_pd_keyboard())
        else:
            await answer(
                OFERTA_GATE_TEXT,
                reply_markup=get_agreement_keyboard(bonus=True),
            )'''
if dont in b:
    b = b.replace(dont, dont_new, 1)
    print("ok dontsign")

cmd = '''    await message.answer("Ознакомиться с доп. соглашением можно по ссылке:\\n"
                         "https://telegra.ph/Polzovatelskoe-soglashenie-01-21-11")'''
cmd_real = '    await message.answer("Ознакомиться с доп. соглашением можно по ссылке:\\n"\n                         "https://telegra.ph/Polzovatelskoe-soglashenie-01-21-11")'
# exact from file
cmd_needle = 'https://telegra.ph/Polzovatelskoe-soglashenie-01-21-11")'
if "telegra.ph/Polzovatelskoe" in b:
    start = b.find("@dp.message(Command('agreement'))")
    chunk = b[start:start+500]
    old_cmd = '''    await message.answer("Ознакомиться с доп. соглашением можно по ссылке:\\n"
                         "https://telegra.ph/Polzovatelskoe-soglashenie-01-21-11")'''
    # try actual newlines in python source for the two-string concat
    i = b.find("https://telegra.ph/Polzovatelskoe-soglashenie-01-21-11")
    print("telegra at", i)
    # replace remaining telegraph urls
    b = b.replace(
        "https://telegra.ph/Polzovatelskoe-soglashenie-01-21-11",
        "https://followthefrensy.ru/oferta",
    )
    print("ok telegraph urls")

bot.write_text(b, encoding="utf-8")
print("bot written", bot.stat().st_size)
