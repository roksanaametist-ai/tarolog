# -*- coding: utf-8 -*-
from pathlib import Path
import shutil
from datetime import datetime

p = Path("/opt/targpt/main.py")
bak = Path(f"/opt/targpt/main.py.bak-tb-{datetime.utcnow().strftime('%Y%m%d%H%M')}")
shutil.copy2(p, bak)
t = p.read_text(encoding="utf-8")

old_mgr = '''    def has_pd_consent(self, user_id):
        v = self.load_agreements().get(str(user_id))
        return v is True or v == "pd"

    def add_pd_consent(self, user_id):
        if self.user_has_agreed(user_id):
            return
        agreements = self.load_agreements()
        agreements[str(user_id)] = "pd"
        self.save_agreements(agreements)

    def add_user_agreement(self, user_id):
'''
new_mgr = '''    def has_pd_consent(self, user_id):
        v = self.load_agreements().get(str(user_id))
        return v is True or v in ("pd", "tb")

    def has_tb_consent(self, user_id):
        v = self.load_agreements().get(str(user_id))
        return v is True or v == "tb"

    def add_pd_consent(self, user_id):
        if self.user_has_agreed(user_id) or self.has_tb_consent(user_id):
            return
        agreements = self.load_agreements()
        agreements[str(user_id)] = "pd"
        self.save_agreements(agreements)

    def add_tb_consent(self, user_id):
        if self.user_has_agreed(user_id):
            return
        agreements = self.load_agreements()
        agreements[str(user_id)] = "tb"
        self.save_agreements(agreements)

    def add_user_agreement(self, user_id):
'''
if old_mgr not in t:
    raise SystemExit("manager block not found")
t = t.replace(old_mgr, new_mgr, 1)

old_pd = '''PD_GATE_TEXT = (
    "Чтобы пользоваться ботом, нужно отдельное согласие на обработку персональных данных.\\n\\n"
    f"Политика: {PRIVACY_URL}\\n\\n"
    "Нажимая кнопку, вы соглашаетесь на обработку данных для услуги "
    "(мессенджеры, баланс, переписка; часть данных может уходить за рубеж — см. политику)."
)
OFERTA_GATE_TEXT = (
'''
new_pd = '''PD_GATE_TEXT = (
    "Чтобы пользоваться ботом, нужно отдельное согласие на обработку персональных данных.\\n\\n"
    f"Политика: {PRIVACY_URL}\\n\\n"
    "Нажимая кнопку, вы соглашаетесь на обработку данных для услуги "
    "(мессенджеры, баланс, переписка). Это не оферта и не согласие на передачу за рубеж."
)
TB_GATE_TEXT = (
    "Отдельно нужно согласие на трансграничную передачу персональных данных.\\n\\n"
    "Идентификатор, ник и текст обращения передаются в Telegram и могут идти через "
    "сервер в Германии; текст вопроса — к языковой модели за рубежом. "
    f"Подробности: {PRIVACY_URL}\\n\\n"
    "Нажимая кнопку, вы даёте согласие именно на такую передачу. Это не оферта."
)
OFERTA_GATE_TEXT = (
'''
if old_pd not in t:
    raise SystemExit("PD_GATE_TEXT not found")
t = t.replace(old_pd, new_pd, 1)

old_kb = '''def get_pd_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Согласен на обработку ПД", callback_data="agree_pd")
    builder.button(text="❌ Отказаться", callback_data="disagree")
    builder.adjust(1)
    return builder.as_markup()
'''
new_kb = '''def get_pd_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Согласен на обработку ПД", callback_data="agree_pd")
    builder.button(text="❌ Отказаться", callback_data="disagree")
    builder.adjust(1)
    return builder.as_markup()


def get_tb_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Согласен на передачу за рубеж", callback_data="agree_tb")
    builder.button(text="❌ Отказаться", callback_data="disagree")
    builder.adjust(1)
    return builder.as_markup()
'''
if old_kb not in t:
    raise SystemExit("pd keyboard not found")
t = t.replace(old_kb, new_kb, 1)

t = t.replace(
    'F.data.in_(["agree", "disagree", "agree_bonus15", "agree_dontsign", "agree_pd"])',
    'F.data.in_(["agree", "disagree", "agree_bonus15", "agree_dontsign", "agree_pd", "agree_tb"])',
    1,
)

old_pd_cb = '''    if callback.data == "agree_pd":
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
        agreement_manager.add_user_agreement(user_id)
'''
new_pd_cb = '''    if callback.data == "agree_pd":
        agreement_manager.add_pd_consent(user_id)
        await callback.message.answer(TB_GATE_TEXT, reply_markup=get_tb_keyboard())
        await callback.answer()
        return

    if callback.data == "agree_tb":
        if not agreement_manager.has_pd_consent(user_id):
            await callback.message.answer(PD_GATE_TEXT, reply_markup=get_pd_keyboard())
            await callback.answer()
            return
        agreement_manager.add_tb_consent(user_id)
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
        if not agreement_manager.has_tb_consent(user_id):
            await callback.message.answer(TB_GATE_TEXT, reply_markup=get_tb_keyboard())
            await callback.answer()
            return
        agreement_manager.add_user_agreement(user_id)
'''
if old_pd_cb not in t:
    raise SystemExit("callback block not found")
t = t.replace(old_pd_cb, new_pd_cb, 1)

# start / other gates: after PD, require TB before oferta
old_start = '''        if not agreement_manager.has_pd_consent(user_id):
            await message.answer(PD_GATE_TEXT, reply_markup=get_pd_keyboard())
        elif agree15:
'''
new_start = '''        if not agreement_manager.has_pd_consent(user_id):
            await message.answer(PD_GATE_TEXT, reply_markup=get_pd_keyboard())
        elif not agreement_manager.has_tb_consent(user_id):
            await message.answer(TB_GATE_TEXT, reply_markup=get_tb_keyboard())
        elif agree15:
'''
n = t.count(old_start)
if n != 1:
    raise SystemExit(f"start gate count {n}")
t = t.replace(old_start, new_start, 1)

old_ds = '''        if not agreement_manager.has_pd_consent(chat_id):
            await answer(PD_GATE_TEXT, reply_markup=get_pd_keyboard())
        else:
            await answer(
                OFERTA_GATE_TEXT,
                reply_markup=get_agreement_keyboard(bonus=True),
            )
'''
new_ds = '''        if not agreement_manager.has_pd_consent(chat_id):
            await answer(PD_GATE_TEXT, reply_markup=get_pd_keyboard())
        elif not agreement_manager.has_tb_consent(chat_id):
            await answer(TB_GATE_TEXT, reply_markup=get_tb_keyboard())
        else:
            await answer(
                OFERTA_GATE_TEXT,
                reply_markup=get_agreement_keyboard(bonus=True),
            )
'''
if old_ds not in t:
    raise SystemExit("dont_sign gate not found")
t = t.replace(old_ds, new_ds, 1)

p.write_text(t, encoding="utf-8")
print("bot patched", "bak", bak.name, "tb_gate", "TB_GATE_TEXT" in t, "agree_tb", t.count("agree_tb"))
