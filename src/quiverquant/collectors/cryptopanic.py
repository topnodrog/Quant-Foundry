"""CryptoPanic — community sentiment (Panic Score). PLAN.md §2 #4.

CryptoPanic's v2 API requires an auth_token on every request, even on the
free plan (no keyless tier) — untested here, no key available. Sign up free
at https://cryptopanic.com/developers/api/ and set CRYPTOPANIC_API_KEY.
fetch() returns nothing until that key exists.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable

import requests

from quiverquant.collectors.base import Collector
from quiverquant.config import get_source

BASE = "https://cryptopanic.com/api/v2/posts/"


class CryptoPanicCollector(Collector):
    name = "cryptopanic"

    def __init__(self, currencies: list[str] | None = None, limit: int = 30):
        self.currencies = currencies or ["BTC", "ETH", "SOL"]
        self.limit = limit

    def fetch(self, tier: str) -> Iterable[dict[str, Any]]:
        api_key = get_source(self.name).active_key()
        if not api_key:
            return
        now = datetime.now(timezone.utc)
        resp = requests.get(
            BASE,
            params={"auth_token": api_key, "currencies": ",".join(self.currencies)},
            timeout=30,
        )
        if resp.status_code != 200:
            return
        for post in resp.json().get("results", [])[: self.limit]:
            yield {
                "signal_type": "sentiment_post",
                "entity": ",".join(c["code"] for c in post.get("currencies", []) or []),
                "ts": _parse(post.get("published_at")) or now,
                "payload": {
                    "title": post.get("title"),
                    "url": post.get("url"),
                    "votes": post.get("votes"),
                    "kind": post.get("kind"),
                },
            }


def _parse(value: str | None):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
