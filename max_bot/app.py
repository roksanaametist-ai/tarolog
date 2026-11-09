"""FastAPI webhook server for Follow the Frensy on MAX."""

from __future__ import annotations

import asyncio
import hmac
import logging
import os
from contextlib import asynccontextmanager

from fastapi import BackgroundTasks, FastAPI, Header, Request
from fastapi.responses import JSONResponse, Response

from . import config
from .client import api
from .deck import build_deck, cards_from_webapp_paths
from .handlers import accept_miniapp_cards, dispatch_update
from .init_data import max_user_id
from .jobs import periodic_30day_refill
from .payments import initialize_payment_file, recurring_billing_loop

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger("max_bot")


@asynccontextmanager
async def lifespan(app: FastAPI):
    build_deck()
    initialize_payment_file()
    refill_task = asyncio.create_task(periodic_30day_refill())
    renew_task = asyncio.create_task(recurring_billing_loop())
    logger.info(
        "MAX bot ready. data_dir=%s admins=%s",
        config.DATA_DIR,
        sorted(config.MAX_ADMIN_IDS),
    )
    if not config.MAX_BOT_TOKEN:
        logger.warning("MAX_BOT_TOKEN пуст — отправка сообщений не заработает")
    yield
    refill_task.cancel()
    renew_task.cancel()
    await api.aclose()


app = FastAPI(title="Follow the Frensy MAX", lifespan=lifespan)


def _verify_secret(received: str | None) -> bool:
    expected = config.MAX_WEBHOOK_SECRET
    if not expected:
        insecure = os.getenv("MAX_WEBHOOK_INSECURE", "").strip().lower() in {
            "1",
            "true",
            "yes",
        }
        if insecure:
            logger.warning("MAX_WEBHOOK_SECRET пуст, MAX_WEBHOOK_INSECURE=1 — webhook открыт")
            return True
        logger.error("MAX_WEBHOOK_SECRET не задан — webhook отклонён")
        return False
    if not received:
        return False
    return hmac.compare_digest(received, expected)


@app.get("/health")
async def health():
    return {"ok": True, "service": "follow-the-frensy-max"}


_WEBAPP_CORS = {
    "Access-Control-Allow-Origin": "https://followthefrensy.ru",
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
}


@app.options("/max/webapp")
async def max_webapp_options():
    return Response(status_code=204, headers=_WEBAPP_CORS)


@app.post("/max/webapp")
async def max_webapp(request: Request, background_tasks: BackgroundTasks):
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid json"}, status_code=400, headers=_WEBAPP_CORS)
    if not isinstance(body, dict):
        return JSONResponse({"error": "invalid body"}, status_code=400, headers=_WEBAPP_CORS)
    user_id = max_user_id(str(body.get("init_data") or ""), config.MAX_BOT_TOKEN)
    if user_id is None:
        return JSONResponse({"error": "forbidden"}, status_code=403, headers=_WEBAPP_CORS)
    paths = body.get("cards")
    if not isinstance(paths, list) or not paths:
        return JSONResponse({"error": "cards"}, status_code=400, headers=_WEBAPP_CORS)
    cards = cards_from_webapp_paths([str(item) for item in paths[:12]])
    background_tasks.add_task(accept_miniapp_cards, user_id, cards)
    return JSONResponse({"ok": True}, headers=_WEBAPP_CORS)


@app.post("/max/webhook")
@app.post("/webhook")
async def webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_max_bot_api_secret: str | None = Header(default=None, alias="X-Max-Bot-Api-Secret"),
):
    if not _verify_secret(x_max_bot_api_secret):
        logger.warning("Webhook secret mismatch")
        return JSONResponse({"error": "forbidden"}, status_code=403)

    try:
        data = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid json"}, status_code=400)

    if not isinstance(data, dict):
        return JSONResponse({"error": "invalid body"}, status_code=400)

    update_type = data.get("update_type", "")
    logger.info("update_type=%s", update_type)

    # Acknowledge quickly; process in background (MAX expects 200 within 30s)
    background_tasks.add_task(_safe_dispatch, data)
    return {"ok": True}


async def _safe_dispatch(data: dict) -> None:
    try:
        await dispatch_update(data)
    except Exception:
        logger.exception("Failed to handle update %s", data.get("update_type"))


def main() -> None:
    import uvicorn

    uvicorn.run(
        "max_bot.app:app",
        host=config.MAX_HOST,
        port=config.MAX_PORT,
        reload=False,
    )


if __name__ == "__main__":
    main()
