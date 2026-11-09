"""Crypto Pay (@CryptoBot) invoices priced in RUB."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import urllib.error
import urllib.request
from typing import Any, Optional


class CryptoPayError(RuntimeError):
    pass


def _env(name: str, default: str = "") -> str:
    return (os.getenv(name) or default).strip()


def is_configured() -> bool:
    return bool(_env("CRYPTO_PAY_TOKEN"))


def api_base() -> str:
    return _env("CRYPTO_PAY_API_BASE", "https://pay.crypt.bot/api").rstrip("/")


def _token() -> str:
    token = _env("CRYPTO_PAY_TOKEN")
    if not token:
        raise CryptoPayError("CRYPTO_PAY_TOKEN не задан")
    return token


def verify_webhook(raw_body: bytes, signature: str) -> bool:
    """HMAC-SHA256 of the raw body, key = SHA256(api token)."""
    token = _env("CRYPTO_PAY_TOKEN")
    if not token or not signature:
        return False
    secret = hashlib.sha256(token.encode("utf-8")).digest()
    digest = hmac.new(secret, raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(digest, signature.strip())


def _call(method: str, params: Optional[dict[str, Any]] = None) -> Any:
    url = f"{api_base()}/{method}"
    payload = json.dumps(params or {}, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        method="POST",
        headers={
            "Crypto-Pay-API-Token": _token(),
            "Content-Type": "application/json",
            "User-Agent": "curl/8.4.0",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            body = resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:300]
        raise CryptoPayError(f"Crypto Pay HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise CryptoPayError(f"Crypto Pay недоступен: {exc.reason}") from exc
    try:
        data = json.loads(body)
    except json.JSONDecodeError as exc:
        raise CryptoPayError("Crypto Pay вернул не JSON") from exc
    if not isinstance(data, dict) or not data.get("ok"):
        err = data.get("error") if isinstance(data, dict) else None
        name = err.get("name") if isinstance(err, dict) else str(err or "error")
        raise CryptoPayError(f"Crypto Pay: {name}")
    return data.get("result")


def get_me() -> dict[str, Any]:
    result = _call("getMe")
    return result if isinstance(result, dict) else {}


def create_invoice(
    *,
    amount_rub: str,
    description: str,
    payload: str,
    paid_btn_url: str = "",
) -> dict[str, Any]:
    params: dict[str, Any] = {
        "currency_type": "fiat",
        "fiat": "RUB",
        "amount": amount_rub,
        "description": description[:1024],
        "payload": payload[:4096],
        "allow_comments": False,
        "allow_anonymous": True,
    }
    if paid_btn_url:
        params["paid_btn_name"] = "openBot"
        params["paid_btn_url"] = paid_btn_url
    result = _call("createInvoice", params)
    if not isinstance(result, dict) or not result.get("invoice_id"):
        raise CryptoPayError("Crypto Pay не вернул счёт")
    return result


def get_invoice(invoice_id: int) -> Optional[dict[str, Any]]:
    result = _call("getInvoices", {"invoice_ids": str(int(invoice_id))})
    if isinstance(result, list):
        items = result
    elif isinstance(result, dict) and isinstance(result.get("items"), list):
        items = result["items"]
    else:
        items = []
    for item in items:
        if isinstance(item, dict) and int(item.get("invoice_id") or 0) == int(invoice_id):
            return item
    return None


def pay_url(invoice: dict[str, Any]) -> str:
    for key in ("bot_invoice_url", "mini_app_invoice_url", "web_app_invoice_url", "pay_url"):
        url = str(invoice.get(key) or "").strip()
        if url:
            return url
    raise CryptoPayError("Crypto Pay не вернул ссылку на оплату")
