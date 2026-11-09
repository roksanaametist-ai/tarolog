"""Simple deal board (internal CRM). File: crm_deals.json in DATA_DIR."""

from __future__ import annotations

import json
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

STAGES = ("new", "talk", "paid", "done")
FORMATS = ("q1111", "v5555", "full11111", "tt3333", "bot", "other")

_lock = threading.Lock()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def empty_deal() -> dict:
    return {
        "id": uuid.uuid4().hex[:12],
        "name": "",
        "contact": "",
        "format": "other",
        "stage": "new",
        "amount": 0,
        "note": "",
        "source": "manual",
        "lead_id": "",
        "created_at": _now(),
        "updated_at": _now(),
    }


class CrmStore:
    def __init__(self, path: Path):
        self.path = path

    def _load(self) -> dict:
        if not self.path.exists():
            return {"deals": []}
        try:
            with open(self.path, encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                return {"deals": []}
            deals = data.get("deals")
            if not isinstance(deals, list):
                data["deals"] = []
            return data
        except (json.JSONDecodeError, OSError):
            return {"deals": []}

    def _save(self, data: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".json.tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        tmp.replace(self.path)

    def list_deals(self) -> list[dict]:
        with _lock:
            return list(self._load().get("deals") or [])

    def upsert(self, patch: dict, deal_id: str | None = None) -> dict:
        with _lock:
            data = self._load()
            deals: list = data.setdefault("deals", [])
            found = None
            if deal_id:
                for d in deals:
                    if d.get("id") == deal_id:
                        found = d
                        break
                if found is None:
                    raise KeyError(deal_id)
            else:
                found = empty_deal()
                deals.append(found)
            for key in ("name", "contact", "note", "source", "lead_id"):
                if key in patch and patch[key] is not None:
                    found[key] = str(patch[key]).strip()[:2000 if key == "note" else 200]
            if "format" in patch and patch["format"] in FORMATS:
                found["format"] = patch["format"]
            if "stage" in patch and patch["stage"] in STAGES:
                found["stage"] = patch["stage"]
            if "amount" in patch:
                try:
                    found["amount"] = max(0, int(patch["amount"]))
                except (TypeError, ValueError):
                    pass
            found["updated_at"] = _now()
            self._save(data)
            return dict(found)

    def delete(self, deal_id: str) -> bool:
        with _lock:
            data = self._load()
            deals: list = data.get("deals") or []
            nxt = [d for d in deals if d.get("id") != deal_id]
            if len(nxt) == len(deals):
                return False
            data["deals"] = nxt
            self._save(data)
            return True

    def add_from_lead(self, lead: dict) -> dict | None:
        contact = (lead.get("contact") or "").strip()
        name = (lead.get("name") or "").strip()
        lead_id = str(lead.get("id") or "")
        if not contact and not name:
            return None
        with _lock:
            data = self._load()
            deals: list = data.setdefault("deals", [])
            for d in deals:
                if lead_id and d.get("lead_id") == lead_id:
                    return dict(d)
                if contact and d.get("contact") == contact:
                    return dict(d)
            row = empty_deal()
            row["name"] = name[:80]
            row["contact"] = contact[:120]
            row["source"] = "site"
            row["lead_id"] = lead_id
            row["format"] = "bot"
            row["note"] = "Заявка с сайта"
            deals.append(row)
            self._save(data)
            return dict(row)

    def import_leads(self, leads: list) -> int:
        n = 0
        for lead in leads:
            if self.add_from_lead(lead):
                n += 1
        return n
