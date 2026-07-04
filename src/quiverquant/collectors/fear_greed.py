"""Alternative.me Crypto Fear & Greed index — market-wide sentiment.

Free, no key, no documented rate limit. Refills the sentiment category
(PLAN.md §2 #4) after CryptoPanic was dropped (no free tier, see
collectors/cryptopanic.py). Note this is a single market-wide 0-100 index,
NOT per-token community sentiment like CryptoPanic gave — coarser, but a
genuine free signal and a common regime input.

api.alternative.me/fng returns newest-first daily readings; each has a
string `value` (0-100), a `value_classification` bucket ("Extreme Fear" ..
"Extreme Greed"), and a unix-seconds `timestamp`. Deduped on the reading's
date so repeated same-day runs don't reinsert an unchanged index value.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable

import requests

from quiverquant.collectors.base import Collector
from quiverquant.storage import get_connection

BASE = "https://api.alternative.me/fng/"


class FearGreedCollector(Collector):
    name = "fear_greed"

    def __init__(self, limit: int = 30):
        self.limit = limit

    def fetch(self, tier: str) -> Iterable[dict[str, Any]]:
        resp = requests.get(BASE, params={"limit": self.limit}, timeout=30)
        if resp.status_code != 200:
            return
        seen = _seen_dates()
        for reading in resp.json().get("data", []):
            ts = _parse_ts(reading.get("timestamp"))
            if ts is None or ts.date().isoformat() in seen:
                continue
            yield {
                "signal_type": "fear_greed_index",
                "entity": "market",
                "ts": ts,
                "payload": {
                    "value": _to_int(reading.get("value")),
                    "classification": reading.get("value_classification"),
                    "date": ts.date().isoformat(),
                },
            }


def _seen_dates() -> set[str]:
    con = get_connection()
    try:
        rows = con.execute(
            "SELECT DISTINCT json_extract_string(payload, '$.date') "
            "FROM raw_signals WHERE source = 'fear_greed'"
        ).fetchall()
    finally:
        con.close()
    return {r[0] for r in rows if r[0]}


def _parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromtimestamp(int(value), tz=timezone.utc)
    except (ValueError, TypeError, OSError):
        return None


def _to_int(value: Any) -> int | None:
    try:
        return int(value)
    except (ValueError, TypeError):
        return None
