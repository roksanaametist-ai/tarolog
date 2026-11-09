"""Register HTTPS webhook subscription with MAX Bot API."""

from __future__ import annotations

import argparse
import asyncio
import sys

from . import config
from .client import MaxClient


async def run(url: str, secret: str) -> None:
    if not config.MAX_BOT_TOKEN:
        print("ERROR: MAX_BOT_TOKEN не задан в .env", file=sys.stderr)
        sys.exit(1)
    if not url.startswith("https://"):
        print("ERROR: webhook URL должен быть HTTPS", file=sys.stderr)
        sys.exit(1)

    client = MaxClient()
    try:
        me = await client.get_me()
        print("Bot:", me)
        result = await client.subscribe_webhook(url, secret=secret)
        print("Subscribe result:", result)
        subs = await client.list_subscriptions()
        print("Subscriptions:", subs)
    finally:
        await client.aclose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Register MAX webhook")
    parser.add_argument(
        "--url",
        default=config.MAX_WEBHOOK_URL,
        help="HTTPS webhook URL (e.g. https://followthefrensy.com/max/webhook)",
    )
    parser.add_argument(
        "--secret",
        default=config.MAX_WEBHOOK_SECRET,
        help="Webhook secret (X-Max-Bot-Api-Secret)",
    )
    args = parser.parse_args()
    if not args.url:
        print("ERROR: укажите --url или MAX_WEBHOOK_URL", file=sys.stderr)
        sys.exit(1)
    asyncio.run(run(args.url, args.secret or ""))


if __name__ == "__main__":
    main()
