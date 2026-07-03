"""Nansen + Dune Analytics — smart-money wallet labels + on-chain SQL.
PLAN.md §2 #8.

Dune: free signup gets an API key (DUNE_API_KEY) with a monthly credit
allowance. Query authoring is normally out of scope for this collector (it
executes an existing query and pulls results) — but Dune's Create/Update
Query endpoints turned out to work on this free-tier key despite docs
saying "Analyst plan or higher required" (is_private=True 402'd with "Max
number of private queries reached", is_private=False succeeded), so query
7872020 ("eth whale transfers >500 ETH, 3d window") was created and is
wired in as the default. If DUNE_API_KEY changes to an account without
query 7872020, either recreate a similar query and update
DEFAULT_DUNE_QUERY_IDS, or pass query_ids= explicitly.

Nansen DOES have a free tier (2,000 one-time starter credits + 10/day
refresh, per research/quiverquant-data-landscape.md — corrected from an
earlier "paid only" note in this file) — NANSEN_API_KEY in config.py.
Confirmed live 2026-07-03 against docs.nansen.ai/getting-started/authentication:
POST (not GET) to api.nansen.ai/api/v1/smart-money/holdings, lowercase
`apikey` header (case-sensitive in their middleware — `apiKey` 401s), and
the key itself includes an `nsn_` prefix as part of the literal value (a
prefix-stripped copy of the key 401s too — this cost real debugging time,
don't re-strip it).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable

import requests

from quiverquant.collectors.base import Collector
from quiverquant.config import get_source

DUNE_QUERY_RESULTS = "https://api.dune.com/api/v1/query/{query_id}/results"
NANSEN_SMART_MONEY_HOLDINGS = "https://api.nansen.ai/api/v1/smart-money/holdings"
DEFAULT_NANSEN_CHAINS = ["ethereum"]

# 7872020: "eth whale transfers >500 ETH, 3d window" - raw ethereum.transactions
# scan, no price join, kept cheap on free-tier credits. Owned by the
# DUNE_API_KEY account (junctiongenerator); see docstring above.
DEFAULT_DUNE_QUERY_IDS: list[int] = [7872020]


class SmartMoneyCollector(Collector):
    name = "dune"

    def __init__(
        self,
        query_ids: list[int] | None = None,
        nansen_chains: list[str] | None = None,
    ):
        self.query_ids = query_ids if query_ids is not None else DEFAULT_DUNE_QUERY_IDS
        self.nansen_chains = nansen_chains or DEFAULT_NANSEN_CHAINS

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
                    "entity": _row_entity(row, query_id),
                    "ts": _row_ts(row, now),
                    "payload": row,
                    "source": "dune",
                    "tier": "free",
                }

    def _fetch_nansen(self) -> Iterable[dict[str, Any]]:
        api_key = get_source("nansen").active_key()
        if not api_key:
            return
        now = datetime.now(timezone.utc)
        resp = requests.post(
            NANSEN_SMART_MONEY_HOLDINGS,
            headers={"Content-Type": "application/json", "apikey": api_key},
            json={"chains": self.nansen_chains},
            timeout=30,
        )
        if resp.status_code != 200:
            return
        for row in resp.json().get("data", []):
            yield {
                "signal_type": "smart_money_holding",
                "entity": row.get("token_symbol") or row.get("token_address"),
                "ts": now,
                "payload": row,
                "source": "nansen",
                "tier": get_source("nansen").tier(),
            }


def _row_entity(row: dict[str, Any], query_id: int) -> str:
    for key in ("hash", "tx_hash", "address", "from_address", "wallet"):
        if row.get(key):
            return str(row[key])
    return str(query_id)


def _row_ts(row: dict[str, Any], default: datetime) -> datetime:
    for key in ("block_time", "ts", "timestamp", "time"):
        value = row.get(key)
        if not value:
            continue
        try:
            return datetime.strptime(str(value)[:19], "%Y-%m-%d %H:%M:%S").replace(
                tzinfo=timezone.utc
            )
        except ValueError:
            continue
    return default
