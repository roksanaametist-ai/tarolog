import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request

APP_DIR = Path(__file__).resolve().parent
ROOT_DIR = APP_DIR.parent
load_dotenv(ROOT_DIR / ".env")
load_dotenv()

app = Flask(__name__)

DATA_DIR = Path(os.getenv("LANDING_DATA_DIR", "/data"))
if not DATA_DIR.exists():
    DATA_DIR = APP_DIR

LEADS_FILE = DATA_DIR / "leads.json"
_leads_lock = threading.Lock()

BOT_URL = os.getenv("LANDING_BOT_URL", "https://t.me/follow_the_frensy").strip()
BOT_START_PARAM = os.getenv("LANDING_BOT_START_PARAM", "site").strip()

_SOCIAL_KEYS = (
    ("telegram", "Telegram"),
    ("instagram", "Instagram"),
    ("tiktok", "TikTok"),
    ("vk", "ВК"),
    ("max", "МАКС"),
    ("youtube", "YouTube"),
    ("rutube", "Rutube"),
)


def _social_url(key: str, default: str = "") -> str:
    return os.getenv(f"SOCIAL_{key.upper()}", default).strip()


SOCIAL = {key: _social_url(key, "#") for key, _ in _SOCIAL_KEYS}

CONSULTATION_URL = os.getenv(
    "CONSULTATION_URL", "https://t.me/roxanaametist"
).strip()
SCHOOL_URL = os.getenv("LANDING_SCHOOL_URL", CONSULTATION_URL).strip()


def _bot_deep_link() -> str:
    base = BOT_URL.rstrip("/")
    if not BOT_START_PARAM:
        return base
    sep = "?" if "?" not in base else "&"
    return f"{base}{sep}start={BOT_START_PARAM}"


def _active_social_links() -> list[tuple[str, str, str]]:
    links = []
    for key, label in _SOCIAL_KEYS:
        url = SOCIAL.get(key, "").strip()
        if url and url != "#":
            links.append((key, label, url))
    return links


def _portrait_static_path() -> str:
    images_dir = APP_DIR / "static" / "images"
    for name in ("portrait.jpg", "portrait.jpeg", "portrait.png", "portrait.webp"):
        if (images_dir / name).exists():
            return f"images/{name}"
    return "images/portrait-placeholder.svg"


def _load_leads() -> list:
    if not LEADS_FILE.exists():
        return []
    try:
        with open(LEADS_FILE, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def _save_leads(leads: list) -> None:
    LEADS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(LEADS_FILE, "w", encoding="utf-8") as f:
        json.dump(leads, f, ensure_ascii=False, indent=2)


@app.route("/")
def index():
    return render_template(
        "index.html",
        bot_url=_bot_deep_link(),
        social_links=_active_social_links(),
        consultation_url=CONSULTATION_URL,
        school_url=SCHOOL_URL,
        portrait_path=_portrait_static_path(),
    )


@app.route("/api/lead", methods=["POST"])
def submit_lead():
    payload = request.get_json(silent=True) or {}
    name = (payload.get("name") or "").strip()
    contact = (payload.get("contact") or "").strip()

    if not name or len(name) < 2:
        return jsonify({"ok": False, "error": "Укажите имя"}), 400
    if not contact or len(contact) < 3:
        return jsonify({"ok": False, "error": "Укажите Telegram, WhatsApp или телефон"}), 400

    entry = {
        "id": datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f"),
        "name": name,
        "contact": contact,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "user_agent": (request.headers.get("User-Agent") or "")[:500],
    }

    with _leads_lock:
        leads = _load_leads()
        leads.append(entry)
        _save_leads(leads)

    return jsonify({"ok": True, "bot_url": _bot_deep_link()})


@app.route("/health")
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    app.run(debug=os.getenv("FLASK_DEBUG") == "1", host="0.0.0.0", port=port)
