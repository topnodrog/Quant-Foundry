"""DefiLlama — TVL (free) and token-unlock/emissions data (paid plan only).
PLAN.md §2 #1.

api.llama.fi/protocols is free, no key. api.llama.fi/emissions returns 402
without a DefiLlama pro-plan key (verified 2026-07-02 — PLAN.md's Phase 0
research assumed unlocks were free too; that turned out wrong), so unlocks
only run when tier=="paid" and DEFILLAMA_API_KEY is set.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable

import requests

from quiverquant.collectors.base import Collector
from quiverquant.config import get_source

BASE = "https://api.llama.fi"
EMISSIONS_BASE = "https://api.llama.fi/emissions"
PRO_BASE = "https://pro-api.llama.fi"


class DefiLlamaCollector(Collector):
    name = "defillama"

    def __init__(self, protocol_limit: int = 50, unlock_limit: int = 20):
        self.protocol_limit = protocol_limit
        self.unlock_limit = unlock_limit

    def fetch(self, tier: str) -> Iterable[dict[str, Any]]:
        now = datetime.now(timezone.utc)
        yield from self._fetch_protocols(now)
        if tier == "paid":
            yield from self._fetch_unlocks(now)

    def _fetch_protocols(self, now: datetime) -> Iterable[dict[str, Any]]:
        resp = requests.get(f"{BASE}/protocols", timeout=30)
        resp.raise_for_status()
        protocols = resp.json()[: self.protocol_limit]
        for p in protocols:
            yield {
                "signal_type": "tvl_snapshot",
                "entity": p.get("slug") or p.get("name"),
                "ts": now,
                "payload": {
                    "name": p.get("name"),
                    "symbol": p.get("symbol"),
                    "chain": p.get("chain"),
                    "category": p.get("category"),
                    "tvl": p.get("tvl"),
                    "change_1d": p.get("change_1d"),
                    "change_7d": p.get("change_7d"),
                    "mcap": p.get("mcap"),
                },
            }

    def _fetch_unlocks(self, now: datetime) -> Iterable[dict[str, Any]]:
        api_key = get_source(self.name).paid_key()
        # Untested: no DefiLlama pro key available to verify this path/shape.
        resp = requests.get(f"{PRO_BASE}/{api_key}/api/emissions", timeout=30)
        if resp.status_code != 200:
            return
        data = resp.json()
        protocols = data if isinstance(data, list) else data.get("data", [])
        for p in protocols[: self.unlock_limit]:
            name = p.get("name") if isinstance(p, dict) else None
            if not name:
                continue
            yield {
                "signal_type": "token_unlock_schedule",
                "entity": p.get("gecko_id") or name,
                "ts": now,
                "payload": p,
            }
