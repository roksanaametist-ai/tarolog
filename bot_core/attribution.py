from __future__ import annotations

import re
from dataclasses import asdict, dataclass


CODE_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,23}$")
MAX_START_PAYLOAD = 64


@dataclass(frozen=True)
class StartAttribution:
    source: str
    payload: str
    referrer_id: int | None = None
    partner_code: str | None = None
    campaign_code: str | None = None
    share_pack_id: str | None = None

    def properties(self) -> dict:
        return {key: value for key, value in asdict(self).items() if value is not None}


def normalize_tracking_code(value: str, *, field: str = "code") -> str:
    code = str(value or "").strip().lower().replace("_", "-")
    code = re.sub(r"[^a-z0-9-]+", "-", code).strip("-")
    code = re.sub(r"-{2,}", "-", code)[:24].rstrip("-")
    if not code or not CODE_RE.fullmatch(code):
        raise ValueError(
            f"{field} must contain only latin letters, digits, and hyphens"
        )
    return code


def build_partner_payload(partner_code: str, campaign_code: str | None = None) -> str:
    partner = normalize_tracking_code(partner_code, field="partner")
    payload = f"p_{partner}"
    if campaign_code:
        payload += f"_{normalize_tracking_code(campaign_code, field='campaign')}"
    if len(payload) > MAX_START_PAYLOAD:
        raise ValueError("Telegram start payload exceeds 64 characters")
    return payload


def build_campaign_payload(campaign_code: str) -> str:
    payload = f"c_{normalize_tracking_code(campaign_code, field='campaign')}"
    if len(payload) > MAX_START_PAYLOAD:
        raise ValueError("Telegram start payload exceeds 64 characters")
    return payload


def parse_start_attribution(
    payload: str,
    *,
    landing_param: str = "site",
) -> StartAttribution:
    raw = str(payload or "").strip()[:MAX_START_PAYLOAD]
    if raw.startswith("ref_") and raw[4:].isdigit():
        return StartAttribution("referral", raw, referrer_id=int(raw[4:]))
    if raw.startswith("share_"):
        rest = raw[6:]
        if rest.isdigit():
            return StartAttribution("share", raw, referrer_id=int(rest))
        head, _, tail = rest.partition("_")
        if head.isdigit():
            pack_id = (tail or "").strip()[:32] or None
            return StartAttribution(
                "share",
                raw,
                referrer_id=int(head),
                share_pack_id=pack_id,
            )
    if raw.startswith("p_"):
        parts = raw[2:].split("_", 1)
        try:
            partner = normalize_tracking_code(parts[0], field="partner")
            campaign = (
                normalize_tracking_code(parts[1], field="campaign")
                if len(parts) > 1 and parts[1]
                else None
            )
            return StartAttribution(
                "partner",
                raw,
                partner_code=partner,
                campaign_code=campaign,
            )
        except ValueError:
            return StartAttribution("invalid", raw)
    if raw.startswith("c_"):
        try:
            campaign = normalize_tracking_code(raw[2:], field="campaign")
            return StartAttribution("campaign", raw, campaign_code=campaign)
        except ValueError:
            return StartAttribution("invalid", raw)
    if landing_param and raw == landing_param:
        return StartAttribution("landing", raw, campaign_code="site")
    if raw in {"bonus", "unlim", "referral"}:
        return StartAttribution("campaign", raw, campaign_code=raw)
    if not raw:
        return StartAttribution("direct", "")
    return StartAttribution("other", raw)
