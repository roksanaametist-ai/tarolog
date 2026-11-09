import hashlib
import hmac
import json
import os
import secrets
import threading
from datetime import datetime, timezone
from functools import wraps
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, jsonify, redirect, render_template, request, session, url_for

from crm_store import FORMATS, STAGES, CrmStore
from legal_pages import register_legal

APP_DIR = Path(__file__).resolve().parent
ROOT_DIR = APP_DIR.parent
load_dotenv(ROOT_DIR / ".env")
load_dotenv()

app = Flask(__name__)
register_legal(app)

DATA_DIR = Path(os.getenv("LANDING_DATA_DIR", "/data"))
if not DATA_DIR.exists():
    DATA_DIR = APP_DIR

LEADS_FILE = DATA_DIR / "leads.json"
CRM_FILE = DATA_DIR / "crm_deals.json"
_leads_lock = threading.Lock()
crm = CrmStore(CRM_FILE)

CRM_PASSWORD = (os.getenv("CRM_PASSWORD") or os.getenv("LANDING_CRM_PASSWORD") or "").strip()
app.secret_key = (
    os.getenv("FLASK_SECRET_KEY")
    or os.getenv("LANDING_SECRET_KEY")
    or (hashlib.sha256(("frensy-crm:" + CRM_PASSWORD).encode()).hexdigest() if CRM_PASSWORD else secrets.token_hex(32))
)

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


def _crm_enabled() -> bool:
    return bool(CRM_PASSWORD)


def _crm_login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not _crm_enabled():
            return ("Not found", 404)
        if not session.get("crm_ok"):
            if request.path.startswith("/api/"):
                return jsonify({"ok": False, "error": "auth"}), 401
            return redirect(url_for("crm_login"))
        return view(*args, **kwargs)

    return wrapped


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


def _lead_form_enabled() -> bool:
    return os.getenv("LANDING_SHOW_LEAD_FORM", "0").strip().lower() in ("1", "true", "on", "yes")


@app.route("/api/lead", methods=["POST"])
def submit_lead():
    if not _lead_form_enabled():
        return jsonify({"ok": False, "error": "Форма заявки сейчас закрыта. Напишите в Telegram."}), 403
    payload = request.get_json(silent=True) or {}
    name = (payload.get("name") or "").strip()
    contact = (payload.get("contact") or "").strip()
    consent_pd = payload.get("consent_pd") in (True, 1, "1", "true", "yes", "on")
    consent_tb = payload.get("consent_tb") in (True, 1, "1", "true", "yes", "on")
    consent_oferta = payload.get("consent_oferta") in (True, 1, "1", "true", "yes", "on")

    if not name or len(name) < 2:
        return jsonify({"ok": False, "error": "Укажите имя"}), 400
    if not contact or len(contact) < 3:
        return jsonify({"ok": False, "error": "Укажите Telegram, WhatsApp или телефон"}), 400
    if not consent_pd:
        return jsonify({"ok": False, "error": "Нужно согласие на обработку персональных данных"}), 400
    if not consent_tb:
        return jsonify({"ok": False, "error": "Нужно согласие на трансграничную передачу"}), 400
    if not consent_oferta:
        return jsonify({"ok": False, "error": "Нужно принять оферту"}), 400

    entry = {
        "id": datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f"),
        "name": name,
        "contact": contact,
        "consent_pd": True,
        "consent_tb": True,
        "consent_oferta": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "user_agent": (request.headers.get("User-Agent") or "")[:500],
    }

    with _leads_lock:
        leads = _load_leads()
        leads.append(entry)
        _save_leads(leads)

    try:
        crm.add_from_lead(entry)
    except OSError:
        pass

    return jsonify({"ok": True, "bot_url": _bot_deep_link()})


@app.route("/crm/login", methods=["GET", "POST"])
def crm_login():
    if not _crm_enabled():
        return ("Not found", 404)
    error = ""
    if request.method == "POST":
        given = (request.form.get("password") or "").encode()
        expect = CRM_PASSWORD.encode()
        if hmac.compare_digest(given, expect):
            session["crm_ok"] = True
            session.permanent = True
            return redirect(url_for("crm_board"))
        error = "Неверный пароль"
    return render_template("crm_login.html", error=error)


@app.route("/crm/logout")
def crm_logout():
    session.clear()
    return redirect(url_for("crm_login") if _crm_enabled() else url_for("index"))


@app.route("/crm")
@_crm_login_required
def crm_board():
    return render_template("crm.html")


@app.route("/api/crm/deals", methods=["GET", "POST"])
@_crm_login_required
def crm_deals():
    if request.method == "GET":
        if request.args.get("import_leads") == "1":
            crm.import_leads(_load_leads())
        deals = crm.list_deals()
        deals.sort(key=lambda d: d.get("updated_at") or "", reverse=True)
        return jsonify({"ok": True, "deals": deals, "stages": list(STAGES), "formats": list(FORMATS)})
    payload = request.get_json(silent=True) or {}
    deal = crm.upsert(payload)
    return jsonify({"ok": True, "deal": deal})


@app.route("/api/crm/deals/<deal_id>", methods=["PATCH", "DELETE"])
@_crm_login_required
def crm_deal(deal_id: str):
    if request.method == "DELETE":
        ok = crm.delete(deal_id)
        return jsonify({"ok": ok}), (200 if ok else 404)
    payload = request.get_json(silent=True) or {}
    try:
        deal = crm.upsert(payload, deal_id=deal_id)
    except KeyError:
        return jsonify({"ok": False, "error": "not found"}), 404
    return jsonify({"ok": True, "deal": deal})


@app.route("/run")
def run_game():
    return render_template(
        "run.html",
        year=datetime.now().year,
        canonical_url="https://followthefrensy.ru/run",
    )


@app.route("/health")
def health():
    return jsonify({"status": "ok"})


def _robokassa_params() -> dict:
    if request.method == "POST":
        return {k: request.form.get(k) for k in request.form.keys()}
    return {k: request.args.get(k) for k in request.args.keys()}


@app.route("/robokassa/result", methods=["GET", "POST"])
def robokassa_result():
    """ResultURL: verify signature, grant subscription, reply OK{InvId}."""
    import sys

    root = str(ROOT_DIR)
    if root not in sys.path:
        sys.path.insert(0, root)

    from bot_core import robokassa
    from bot_core.robokassa_fulfill import fulfill_invoice

    params = {k: v for k, v in _robokassa_params().items() if v is not None}
    ok, err = robokassa.verify_result_params(params)
    if not ok:
        return (f"bad request: {err}", 400)

    try:
        inv_id = int(params.get("InvId") or params.get("InvoiceID") or 0)
    except (TypeError, ValueError):
        return ("bad InvId", 400)

    result = fulfill_invoice(inv_id, out_sum=params.get("OutSum"))
    if not result.get("ok"):
        # Unknown InvId — do not ACK, so Robokassa retries while we investigate
        return (f"error: {result.get('error', 'fulfill')}", 400)

    return (f"OK{inv_id}", 200)


@app.route("/crypto/webhook", methods=["POST"])
def crypto_webhook():
    """Crypto Pay invoice_paid. Signature: HMAC-SHA256(body, SHA256(token))."""
    import sys

    root = str(ROOT_DIR)
    if root not in sys.path:
        sys.path.insert(0, root)

    from bot_core import crypto_pay
    from bot_core.crypto_pay_fulfill import fulfill_invoice

    raw = request.get_data() or b""
    signature = request.headers.get("crypto-pay-api-signature", "")
    if not crypto_pay.verify_webhook(raw, signature):
        return ("bad signature", 403)
    try:
        update = json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError:
        return ("bad json", 400)
    if not isinstance(update, dict) or update.get("update_type") != "invoice_paid":
        return jsonify({"ok": True})
    invoice = update.get("payload")
    if not isinstance(invoice, dict):
        return ("bad payload", 400)
    result = fulfill_invoice(invoice)
    if not result.get("ok"):
        return (f"error: {result.get('error', 'fulfill')}", 400)
    return jsonify({"ok": True})


@app.route("/pay/success")
def pay_success():
    bot = _bot_deep_link()
    return (
        "<!doctype html><html lang=ru><meta charset=utf-8>"
        "<meta name=viewport content='width=device-width,initial-scale=1'>"
        "<title>Оплата принята</title>"
        "<body style='font-family:system-ui;background:#050810;color:#e8e0f0;"
        "display:flex;min-height:100vh;align-items:center;justify-content:center;margin:0'>"
        "<div style='max-width:28rem;padding:2rem;text-align:center'>"
        "<h1 style='font-weight:600'>Оплата принята</h1>"
        "<p>Подписка активируется в боте в течение минуты.</p>"
        f"<p><a href='{bot}' style='color:#ffd4a8'>Вернуться в бот</a></p>"
        "</div></body></html>"
    )


@app.route("/pay/fail")
def pay_fail():
    bot = _bot_deep_link()
    return (
        "<!doctype html><html lang=ru><meta charset=utf-8>"
        "<meta name=viewport content='width=device-width,initial-scale=1'>"
        "<title>Оплата не прошла</title>"
        "<body style='font-family:system-ui;background:#050810;color:#e8e0f0;"
        "display:flex;min-height:100vh;align-items:center;justify-content:center;margin:0'>"
        "<div style='max-width:28rem;padding:2rem;text-align:center'>"
        "<h1 style='font-weight:600'>Оплата не прошла</h1>"
        "<p>Можно попробовать ещё раз из бота.</p>"
        f"<p><a href='{bot}' style='color:#ffd4a8'>Вернуться в бот</a></p>"
        "</div></body></html>"
    )


if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    app.run(debug=os.getenv("FLASK_DEBUG") == "1", host="0.0.0.0", port=port)
