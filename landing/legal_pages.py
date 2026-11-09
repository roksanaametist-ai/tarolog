"""Публичные /privacy и /oferta. Подключается из SiteApp."""

from __future__ import annotations

import os

from flask import render_template

OPERATOR_NAME = (
    os.getenv("LEGAL_OPERATOR_NAME", "Роксана Алигайдеровна Аметист").strip()
    or "Роксана Алигайдеровна Аметист"
)
if OPERATOR_NAME == "Роксана Аметист":
    OPERATOR_NAME = "Роксана Алигайдеровна Аметист"
OPERATOR_INN = os.getenv("LEGAL_OPERATOR_INN", "503225242801").strip()
OPERATOR_PHONE = os.getenv("LEGAL_OPERATOR_PHONE", "").strip()
OPERATOR_EMAIL = (
    os.getenv("LEGAL_OPERATOR_EMAIL", "roxanaametist@gmail.com").strip()
    or "roxanaametist@gmail.com"
)
OPERATOR_CITY = os.getenv("LEGAL_OPERATOR_CITY", "Московская область").strip() or "Московская область"
CONTACT_BOT_URL = (
    os.getenv("LANDING_BOT_URL", "https://t.me/Roxanaametist_Taro_bot").strip()
    or "https://t.me/Roxanaametist_Taro_bot"
)
CONTACT_TELEGRAM = (
    os.getenv("CONSULTATION_URL", "https://t.me/roxanaametist").strip()
    or "https://t.me/roxanaametist"
)
SITE_URL = (
    os.getenv("LANDING_PUBLIC_URL") or os.getenv("SITE_URL") or "https://followthefrensy.ru"
).rstrip("/")
PRIVACY_PATH = "/privacy"
OFERTA_PATH = "/oferta"
PRIVACY_EDITION = "26.10.2026"
OFERTA_EDITION = "26.10.2026"


def privacy_url() -> str:
    return f"{SITE_URL}{PRIVACY_PATH}"


def oferta_url() -> str:
    return f"{SITE_URL}{OFERTA_PATH}"


def legal_template_vars(**extra):
    base = {
        "operator_name": OPERATOR_NAME,
        "operator_inn": OPERATOR_INN,
        "operator_phone": OPERATOR_PHONE,
        "operator_email": OPERATOR_EMAIL,
        "operator_city": OPERATOR_CITY,
        "contact_bot_url": CONTACT_BOT_URL,
        "contact_telegram": CONTACT_TELEGRAM,
        "privacy_url": privacy_url(),
        "oferta_url": oferta_url(),
        "privacy_edition": PRIVACY_EDITION,
        "oferta_edition": OFERTA_EDITION,
    }
    base.update(extra)
    return base


def register_legal(app) -> None:
    @app.context_processor
    def _inject_legal():
        return {
            "privacy_url": privacy_url(),
            "oferta_url": oferta_url(),
            "operator_name": OPERATOR_NAME,
            "operator_inn": OPERATOR_INN,
            "operator_phone": OPERATOR_PHONE,
            "operator_email": OPERATOR_EMAIL,
            "operator_city": OPERATOR_CITY,
            "contact_bot_url": CONTACT_BOT_URL,
            "contact_telegram": CONTACT_TELEGRAM,
        }

    @app.route(PRIVACY_PATH)
    def privacy():
        return render_template(
            "privacy.html",
            **legal_template_vars(
                legal_title="Политика обработки персональных данных — Follow the Frensy",
                legal_description="Как Follow the Frensy обрабатывает персональные данные.",
                canonical_url=privacy_url(),
            ),
        )

    @app.route(OFERTA_PATH)
    def oferta():
        return render_template(
            "oferta.html",
            **legal_template_vars(
                legal_title="Публичная оферта — Follow the Frensy",
                legal_description="Договор оказания информационных и консультационных услуг.",
                canonical_url=oferta_url(),
            ),
        )
