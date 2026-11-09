"""Robokassa payment helpers: MD5 signatures, pay URL, recurring charge."""

from __future__ import annotations

import hashlib
import json
import os
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Mapping, Optional


PAYMENT_URL = "https://auth.robokassa.ru/Merchant/Index.aspx"
RECURRING_URL = "https://auth.robokassa.ru/Merchant/Recurring"


def _env(name: str, default: str = "") -> str:
    return (os.getenv(name) or default).strip()


def is_configured() -> bool:
    return bool(_env("ROBOKASSA_LOGIN") and _env("ROBOKASSA_PASSWORD1") and _env("ROBOKASSA_PASSWORD2"))


def is_test_mode() -> bool:
    return _env("ROBOKASSA_IS_TEST", "1").lower() in {"1", "true", "yes", "on"}


def recurring_enabled() -> bool:
    """Requires Robokassa shop approval for recurring (error 34 if off).

    Hard-off until the shop has recurring enabled in Robokassa cabinet.
    Set ROBOKASSA_RECURRING_FORCE=1 only after approval to re-enable.
    """
    if _env("ROBOKASSA_RECURRING_FORCE", "0").lower() not in {"1", "true", "yes", "on"}:
        return False
    return _env("ROBOKASSA_RECURRING", "0").lower() in {"1", "true", "yes", "on"}


def receipt_enabled() -> bool:
    """Attach 54-FZ Receipt nomenclature. Default on; set ROBOKASSA_RECEIPT=0 to disable."""
    return _env("ROBOKASSA_RECEIPT", "1").lower() not in {"0", "false", "no", "off"}


def _password1() -> str:
    if is_test_mode():
        return _env("ROBOKASSA_TEST_PASSWORD1") or _env("ROBOKASSA_PASSWORD1")
    return _env("ROBOKASSA_PASSWORD1")


def _password2() -> str:
    if is_test_mode():
        return _env("ROBOKASSA_TEST_PASSWORD2") or _env("ROBOKASSA_PASSWORD2")
    return _env("ROBOKASSA_PASSWORD2")


def _sorted_shp(shp: Optional[Mapping[str, str]]) -> list[tuple[str, str]]:
    if not shp:
        return []
    items = []
    for key, value in shp.items():
        name = key if key.startswith("Shp_") else f"Shp_{key}"
        items.append((name, str(value)))
    items.sort(key=lambda kv: kv[0].lower())
    return items


def _md5(text: str) -> str:
    return hashlib.md5(text.encode("utf-8")).hexdigest()


def build_receipt_json(
    *,
    name: str,
    amount_rub: float | int | str,
    tax: Optional[str] = None,
    sno: Optional[str] = None,
) -> str:
    """Compact Receipt JSON for fiscalization (54-FZ nomenclature)."""
    item = {
        "name": (name or "Подписка")[:128],
        "quantity": 1,
        "sum": float(f"{float(amount_rub):.2f}"),
        "payment_method": _env("ROBOKASSA_PAYMENT_METHOD", "full_payment") or "full_payment",
        "payment_object": _env("ROBOKASSA_PAYMENT_OBJECT", "service") or "service",
        "tax": (tax or _env("ROBOKASSA_TAX", "none") or "none"),
    }
    data: dict = {"items": [item]}
    sno_val = (sno if sno is not None else _env("ROBOKASSA_SNO", "")).strip()
    if sno_val:
        data["sno"] = sno_val
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"))


def encode_receipt(receipt_json: str) -> str:
    """URL-encode Receipt JSON for SignatureValue and request body (Robokassa docs)."""
    return urllib.parse.quote(receipt_json, safe="")


def sign_payment(
    out_sum: str,
    inv_id: int,
    shp: Optional[Mapping[str, str]] = None,
    *,
    receipt_encoded: Optional[str] = None,
) -> str:
    """SignatureValue for payment / recurring request (Password #1).

    With Receipt: MerchantLogin:OutSum:InvId:Receipt:Password1[:Shp_*]
    Receipt must already be URL-encoded (same string as the Receipt form field).
    Recurring is NOT a signature modifier — only a request parameter.
    """
    parts = [_env("ROBOKASSA_LOGIN"), str(out_sum), str(int(inv_id))]
    if receipt_encoded is not None:
        parts.append(receipt_encoded)
    parts.append(_password1())
    for name, value in _sorted_shp(shp):
        parts.append(f"{name}={value}")
    return _md5(":".join(parts))


def sign_result(out_sum: str, inv_id: int, shp: Optional[Mapping[str, str]] = None) -> str:
    """SignatureValue check for ResultURL (Password #2)."""
    parts = [str(out_sum), str(int(inv_id)), _password2()]
    for name, value in _sorted_shp(shp):
        parts.append(f"{name}={value}")
    return _md5(":".join(parts))


def extract_shp(params: Mapping[str, str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for key, value in params.items():
        if key.lower().startswith("shp_"):
            # Preserve canonical Shp_ prefix casing from Robokassa docs
            canon = "Shp_" + key[4:] if key[:4].lower() == "shp_" else key
            out[canon] = str(value)
    return out


def format_out_sum(amount_rub: float | int | str) -> str:
    return f"{float(amount_rub):.2f}"


@dataclass(frozen=True)
class PaymentLink:
    inv_id: int
    out_sum: str
    url: str
    signature: str


def build_payment_link(
    *,
    inv_id: int,
    amount_rub: float | int,
    description: str,
    shp: Mapping[str, str],
    email: Optional[str] = None,
    recurring: bool = False,
) -> PaymentLink:
    if not is_configured():
        raise ValueError("Robokassa: задайте ROBOKASSA_LOGIN / PASSWORD1 / PASSWORD2")

    out_sum = format_out_sum(amount_rub)
    shp_map = {(k if k.startswith("Shp_") else f"Shp_{k}"): str(v) for k, v in shp.items()}
    use_recurring = bool(recurring and recurring_enabled())
    # Docs: Receipt value is URL-encoded JSON; same string goes into SignatureValue.
    # urlencode() then percent-encodes "%" again for GET → %257B… (official examples).
    receipt_enc: Optional[str] = None
    if receipt_enabled():
        receipt_enc = encode_receipt(build_receipt_json(name=description, amount_rub=amount_rub))

    signature = sign_payment(out_sum, inv_id, shp_map, receipt_encoded=receipt_enc)

    payload: dict[str, str] = {
        "MerchantLogin": _env("ROBOKASSA_LOGIN"),
        "OutSum": out_sum,
        "InvId": str(int(inv_id)),
        "Description": description[:100],
        "SignatureValue": signature,
        "Culture": "ru",
        "Encoding": "utf-8",
    }
    if receipt_enc is not None:
        payload["Receipt"] = receipt_enc
    if use_recurring:
        payload["Recurring"] = "true"
    if is_test_mode():
        payload["IsTest"] = "1"
    if email:
        payload["Email"] = email
    for name, value in _sorted_shp(shp_map):
        payload[name] = value

    return PaymentLink(
        inv_id=int(inv_id),
        out_sum=out_sum,
        url=f"{PAYMENT_URL}?{urllib.parse.urlencode(payload)}",
        signature=signature,
    )


def verify_result_params(params: Mapping[str, str]) -> tuple[bool, Optional[str]]:
    """Return (ok, error). params are form/query keys from ResultURL."""
    try:
        out_sum = str(params.get("OutSum") or "")
        inv_raw = params.get("InvId") or params.get("InvoiceID") or ""
        inv_id = int(inv_raw)
        got = (params.get("SignatureValue") or "").lower()
    except (TypeError, ValueError):
        return False, "bad params"

    shp = extract_shp(params)
    expect = sign_result(out_sum, inv_id, shp).lower()
    if got != expect:
        return False, "bad signature"
    return True, None


def request_recurring(
    *,
    inv_id: int,
    previous_invoice_id: int,
    amount_rub: float | int,
    description: str,
    shp: Mapping[str, str],
) -> str:
    """POST child recurring charge. Returns response body text."""
    if not is_configured():
        raise ValueError("Robokassa not configured")

    out_sum = format_out_sum(amount_rub)
    shp_map = {(k if k.startswith("Shp_") else f"Shp_{k}"): str(v) for k, v in shp.items()}
    receipt_enc: Optional[str] = None
    if receipt_enabled():
        receipt_enc = encode_receipt(build_receipt_json(name=description, amount_rub=amount_rub))
    signature = sign_payment(out_sum, inv_id, shp_map, receipt_encoded=receipt_enc)

    payload: dict[str, str] = {
        "MerchantLogin": _env("ROBOKASSA_LOGIN"),
        "OutSum": out_sum,
        "InvoiceID": str(int(inv_id)),
        "PreviousInvoiceID": str(int(previous_invoice_id)),
        "Description": description[:100],
        "SignatureValue": signature,
    }
    if receipt_enc is not None:
        payload["Receipt"] = receipt_enc
    for name, value in _sorted_shp(shp_map):
        payload[name] = value

    data = urllib.parse.urlencode(payload).encode("utf-8")
    req = urllib.request.Request(
        RECURRING_URL,
        data=data,
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8", errors="replace")
