"""Validate MAX miniapp initData and return the user id."""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from urllib.parse import unquote


def max_user_id(init_data: str, bot_token: str, *, max_age: int = 3600) -> int | None:
    if not init_data or not bot_token:
        return None
    pairs: list[tuple[str, str]] = []
    for part in init_data.split("&"):
        if "=" not in part:
            continue
        key, value = part.split("=", 1)
        pairs.append((key, unquote(value)))
    hashes = [value for key, value in pairs if key == "hash"]
    if len(hashes) != 1:
        return None
    launch = "\n".join(
        f"{key}={value}"
        for key, value in sorted((key, value) for key, value in pairs if key != "hash")
    )
    secret = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    digest = hmac.new(secret, launch.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(digest, hashes[0]):
        return None
    data = dict(pairs)
    try:
        auth_date = int(data.get("auth_date") or 0)
    except ValueError:
        return None
    if auth_date <= 0 or abs(int(time.time()) - auth_date) > max_age:
        return None
    try:
        user = json.loads(data.get("user") or "")
    except json.JSONDecodeError:
        return None
    if not isinstance(user, dict):
        return None
    raw_id = user.get("id", user.get("user_id"))
    try:
        return int(raw_id)
    except (TypeError, ValueError):
        return None
