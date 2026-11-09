from pathlib import Path

landing = Path("/root/tarolog/landing")
bak = landing / "SiteApp.py.bak-design-20261027-145156"
target = landing / "SiteApp.py"
broken = landing / "SiteApp.py.bak-broken-local-slim"

if target.exists() and not broken.exists():
    broken.write_bytes(target.read_bytes())

text = bak.read_text(encoding="utf-8")
if "from pathlib import Path" not in text[:1200]:
    text = "from pathlib import Path\n" + text

block = '''

def _robokassa_params():
    from flask import request
    if request.method == "POST":
        return {k: request.form.get(k) for k in request.form.keys()}
    return {k: request.args.get(k) for k in request.args.keys()}


@app.route("/robokassa/result", methods=["GET", "POST"])
def robokassa_result():
    """ResultURL: verify signature, grant subscription, reply OK{InvId}."""
    import sys
    root = str(ROOT_DIR) if "ROOT_DIR" in globals() else str(Path(__file__).resolve().parent.parent)
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
        return (f"error: {result.get('error', 'fulfill')}", 400)
    return (f"OK{inv_id}", 200)


@app.route("/pay/success")
def pay_success():
    bot = _bot_deep_link() if "_bot_deep_link" in globals() else BOT_URL
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
    bot = _bot_deep_link() if "_bot_deep_link" in globals() else BOT_URL
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


'''

if '@app.route("/robokassa/result"' not in text:
    marker = 'if __name__ == "__main__":'
    if marker in text:
        text = text.replace(marker, block + marker, 1)
    else:
        text = text.rstrip() + "\n" + block

target.write_text(text, encoding="utf-8")
print("wrote", target, "bytes", target.stat().st_size)
