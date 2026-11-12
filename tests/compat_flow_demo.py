"""Демо-прогон «Совместимости» без боевого токена: лог переписки обоих людей.

python tests/compat_flow_demo.py [путь_к_логу]
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tests import compat_harness as h  # noqa: E402  (ставит тестовое окружение)
import asyncio  # noqa: E402

main, session = h.setup_main()
loop = asyncio.new_event_loop()

A, B = 8_100_001, 8_100_002  # Роксана (старый пользователь) и Анна (новая)
NAMES = {A: "Роксана", B: "Анна"}


def feed(update) -> None:
    loop.run_until_complete(main.dp.feed_update(main.bot, update))


def step(title: str, update) -> None:
    session.calls.append({"method": "STEP", "chat_id": None, "text": title, "buttons": []})
    feed(update)


def render() -> str:
    out = []
    for c in session.calls:
        if c["method"] == "STEP":
            out.append(f"\n=== {c['text']} ===")
            continue
        if c["method"] in {"AnswerCallbackQuery", "SendChatAction", "DeleteMessage", "GetMe",
                           "EditMessageReplyMarkup", "DeleteMessages"}:
            continue
        who = NAMES.get(c["chat_id"], c["chat_id"])
        text = (c.get("text") or "").strip()
        photo = f" [фото {c['photo']}]" if c.get("photo") else ""
        out.append(f"→ {who}: {c['method']}{photo}\n    " + text.replace("\n", "\n    "))
        for row in c["buttons"]:
            out.append("    [" + "] [".join(
                b.get("text", "") + (f" → {b['url'][:60]}…" if b.get("url") else "") for b in row
            ) + "]")
    return "\n".join(out)


def main_run(log_path: Path) -> None:
    main.user_data.add_user(A)
    main.agreement_manager.add_user_agreement(A)
    main.user_data.increment_user_questions(A, 2)
    bal_a0 = main.user_data.get_user_questions(A)

    step("Роксана жмёт «💞 Совместимость»", h.msg_update(A, main.COMPAT_BUTTON, first_name="Роксана"))
    step("Роксана выбирает «Любовь»", h.cb_update(A, "compat_topic:love", first_name="Роксана"))
    step("Роксана: «Да» (это я)", h.cb_update(A, "compat_self_yes", first_name="Роксана"))
    step("Роксана пишет имя партнёра", h.msg_update(A, "Анна", first_name="Роксана"))
    inv_id = session.find_button(A, "compat_inv:")["data"].split(":", 1)[1]
    bal_a1 = main.user_data.get_user_questions(A)
    step("Роксана жмёт «Позвать Анна»", h.cb_update(A, f"compat_inv:{inv_id}", first_name="Роксана"))

    step("Анна (новая) открывает ссылку", h.msg_update(B, f"/start compat_{inv_id}", first_name="Анна"))
    agree = session.find_button(B, "agree")["data"]
    step("Анна принимает соглашение", h.cb_update(B, agree, first_name="Анна"))
    step("Анна жмёт «Посмотреть»", h.cb_update(B, f"compat_view:{inv_id}", first_name="Анна"))
    bal_b0 = main.user_data.get_user_questions(B)
    step("Анна: «Да» (это я)", h.cb_update(B, f"compat_inv_yes:{inv_id}", first_name="Анна"))
    step("Анна жмёт «Сторис»", h.cb_update(B, f"compat_story:{inv_id}", first_name="Анна"))
    step("Анна открывает ссылку ещё раз", h.msg_update(B, f"/start compat_{inv_id}", first_name="Анна"))
    step("Роксана открывает свою ссылку", h.msg_update(A, f"/start compat_{inv_id}", first_name="Роксана"))

    summary = [
        "ИТОГ БАЛАНСОВ",
        f"Роксана: было {bal_a0}, после короткого {bal_a1}, в конце {main.user_data.get_user_questions(A)}"
        f" (−1 за короткий, +{main.REFERRAL_JOIN_BONUS} за нового друга)",
        f"Анна: перед полным {bal_b0}, после {main.user_data.get_user_questions(B)} (полный — бесплатно)",
        f"Анна — реферал Роксаны: {main.user_data.get_referred_by(B) == A}",
        "",
        "ВОРОНКА (события за 7 дней):",
    ]
    for name, row in main.compat_funnel_counts(7).items():
        summary.append(f"  {name}: {row}")
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text("\n".join(summary) + "\n\nПЕРЕПИСКА\n" + render() + "\n", encoding="utf-8")
    print(f"log: {log_path}")


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("D:/Песочницы/compat-run/flow-log.txt")
    main_run(target)
