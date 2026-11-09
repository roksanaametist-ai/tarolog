import hashlib
import importlib.util
import os
import sys
import urllib.parse

os.environ["ROBOKASSA_LOGIN"] = "followthefrensy"
os.environ["ROBOKASSA_PASSWORD1"] = "testpass1"
os.environ["ROBOKASSA_PASSWORD2"] = "testpass2"
os.environ["ROBOKASSA_IS_TEST"] = "0"
os.environ["ROBOKASSA_RECEIPT"] = "1"
os.environ["ROBOKASSA_TAX"] = "none"
os.environ["ROBOKASSA_RECURRING_FORCE"] = "0"

spec = importlib.util.spec_from_file_location(
    "robokassa",
    r"C:\Users\roxan\Projects\TarGPT3\bot_core\robokassa.py",
)
m = importlib.util.module_from_spec(spec)
sys.modules["robokassa"] = m
spec.loader.exec_module(m)

# Official PHP-style: Receipt in payload is already URL-encoded.
receipt_json = m.build_receipt_json(name="product", amount_rub=8.96)
receipt_enc = m.encode_receipt(receipt_json)
assert receipt_enc.startswith("%7B"), receipt_enc[:20]
raw = f"demo:8.96:12345:{receipt_enc}:password_1:Shp_item=digital"
# sanity vs docs sample shape
assert "%22items%22" in receipt_enc

link = m.build_payment_link(
    inv_id=42,
    amount_rub=555,
    description="Подписка 555",
    shp={"chat_id": "1", "plan": "month"},
)
assert "Receipt=" in link.url
# GET must double-encode: %25 for the % of first encoding
assert "%257B" in link.url or "%257b" in link.url.lower(), link.url[:200]
receipt_enc2 = m.encode_receipt(m.build_receipt_json(name="Подписка 555", amount_rub=555))
expect = hashlib.md5(
    f"followthefrensy:555.00:42:{receipt_enc2}:testpass1:Shp_chat_id=1:Shp_plan=month".encode()
).hexdigest()
print("sig_ok", link.signature == expect, link.signature)
print("double_encoded_in_url", "%257B" in link.url)
print("receipt_enc_prefix", receipt_enc2[:40])
