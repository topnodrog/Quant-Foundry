"""Nansen (paid API, no free tier) + Dune Analytics (free tier w/ API key).
PLAN.md §2 #8 — smart-money wallet labels + flexible on-chain SQL.

Dune: free signup gets an API key (DUNE_API_KEY) with a monthly credit
allowance; querying requires a pre-built Dune query ID (query authoring is
out of scope for this collector — it executes an existing query and pulls
results). Untested here, no key available.

Nansen: their public API is paid-only, no free key tier as of this
research — NANSEN_PAID_API_KEY in config.py reflects that (no free_key_env
distinction like other sources). Not implemented until that's provisioned.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable

import requests

from quiverquant.collectors.base import Collector
from quiverquant.config import get_source

DUNE_QUERY_RESULTS = "https://api.dune.com/api/v1/query/{query_id}/results"

# TODO: populate with real saved Dune query IDs (e.g. smart-money wallet
# labels, whale accumulation dashboards) once DUNE_API_KEY is available.
DEFAULT_DUNE_QUERY_IDS: list[int] = []


class SmartMoneyCollector(Collector):
    name = "dune"

    def __init__(self, query_ids: list[int] | None = None):
        self.query_ids = query_ids if query_ids is not None else DEFAULT_DUNE_QUERY_IDS

    def fetch(self, tier: str) -> Iterable[dict[str, Any]]:
        api_key = get_source(self.name).active_key()
        if not api_key or not self.query_ids:
            return
        now = datetime.now(timezone.utc)
        headers = {"X-Dune-API-Key": api_key}
        for query_id in self.query_ids:
            resp = requests.get(
                DUNE_QUERY_RESULTS.format(query_id=query_id), headers=headers, timeout=60
            )
            if resp.status_code != 200:
                continue
            rows = resp.json().get("result", {}).get("rows", [])
            for row in rows:
                yield {
                    "signal_type": "dune_query_row",
                    "entity": str(query_id),
                    "ts": now,
                    "payload": row,
                }
