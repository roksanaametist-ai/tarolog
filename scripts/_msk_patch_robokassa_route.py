"""Insert Robokassa ResultURL route into Moscow landing SiteApp.py."""
from pathlib import Path

path = Path("/opt/targpt/landing/SiteApp.py")
text = path.read_text(encoding="utf-8")
if "robokassa/result" in text:
    print("already patched")
    raise SystemExit(0)

marker = '\n\nif __name__ == "__main__":'
if marker not in text:
    raise SystemExit("marker not found")

# Ensure pathlib Path / ROOT_DIR exist
if "ROOT_DIR" not in text:
    insert_root = (
        "\nfrom pathlib import Path\n"
        "ROOT_DIR = Path(__file__).resolve().parent.parent\n"
    )
    # after first imports block — put near app =
    text = text.replace("app = Flask(__name__)", insert_root + "app = Flask(__name__)", 1)

block = '''

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
        return (f"error: {result.get('error', 'fulfill')}", 400)

    return (f"OK{inv_id}", 200)

'''

text = text.replace(marker, block + marker, 1)
path.write_text(text, encoding="utf-8")
print("patched", path)
