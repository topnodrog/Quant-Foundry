"""Nansen + Dune Analytics — smart-money wallet labels + on-chain SQL.
PLAN.md §2 #8.

Dune: free signup gets an API key (DUNE_API_KEY) with a monthly credit
allowance; querying requires a pre-built Dune query ID (query authoring is
out of scope for this collector — it executes an existing query and pulls
results). Key confirmed valid 2026-07-02 (auth passes; a dummy query ID
returned "no execution found" rather than an auth error) but
DEFAULT_DUNE_QUERY_IDS is still empty — need a real saved query ID from the
dune.com "junctiongenerator" account before this yields data.

Nansen DOES have a free tier (2,000 one-time starter credits + 10/day
refresh, per research/quiverquant-data-landscape.md — corrected from an
earlier "paid only" note in this file) — NANSEN_API_KEY in config.py. Exact
endpoint paths for Smart Money/Wallet Profiler weren't pinned down during
research (docs.nansen.ai lists categories, not a full path reference), so
_fetch_nansen's URL is a best guess and untested; confirm against the docs
once a key exists.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable

import requests

from quiverquant.collectors.base import Collector
from quiverquant.config import get_source

DUNE_QUERY_RESULTS = "https://api.dune.com/api/v1/query/{query_id}/results"
NANSEN_SMART_MONEY = "https://api.nansen.ai/api/v1/smart-money/inflows"

# TODO: populate with real saved Dune query IDs (e.g. smart-money wallet
# labels, whale accumulation dashboards) once DUNE_API_KEY is available.
DEFAULT_DUNE_QUERY_IDS: list[int] = []


class SmartMoneyCollector(Collector):
    name = "dune"

    def __init__(self, query_ids: list[int] | None = None):
        self.query_ids = query_ids if query_ids is not None else DEFAULT_DUNE_QUERY_IDS

    def fetch(self, tier: str) -> Iterable[dict[str, Any]]:
        yield from self._fetch_dune()
        yield from self._fetch_nansen()

    def _fetch_dune(self) -> Iterable[dict[str, Any]]:
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
                    "source": "dune",
                    "tier": "free",
                }

    def _fetch_nansen(self) -> Iterable[dict[str, Any]]:
        api_key = get_source("nansen").active_key()
        if not api_key:
            return
        now = datetime.now(timezone.utc)
        # TODO(untested, no key available): confirm URL/params/response shape
        # against https://docs.nansen.ai/ once NANSEN_API_KEY is set.
        resp = requests.get(
            NANSEN_SMART_MONEY, headers={"apiKey": api_key}, timeout=30
        )
        if resp.status_code != 200:
            return
        for row in resp.json().get("data", []):
            yield {
                "signal_type": "smart_money_inflow",
                "entity": row.get("token_symbol") or row.get("address"),
                "ts": now,
                "payload": row,
                "source": "nansen",
                "tier": get_source("nansen").tier(),
            }
