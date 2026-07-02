"""Etherscan V2 (needs free key) + Blockchair (keyless free tier).
PLAN.md §2 #3 — wallet/tx base layer.

Blockchair's basic stats endpoints work with no key at low volume, verified
2026-07-02, so that half runs today. Etherscan V2's unified multi-chain API
requires a free-signup key (ETHERSCAN_API_KEY) — untested here, no key
available; fetch() skips it silently when the key is absent rather than
failing the whole collector run.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable

import requests

from quiverquant.collectors.base import Collector
from quiverquant.config import get_source

BLOCKCHAIR_BASE = "https://api.blockchair.com"
ETHERSCAN_V2_BASE = "https://api.etherscan.io/v2/api"

DEFAULT_BLOCKCHAIR_CHAINS = ["bitcoin", "ethereum"]
# chainid per https://api.etherscan.io/v2 docs: 1=Ethereum mainnet
DEFAULT_ETHERSCAN_CHAIN_IDS = [1]


class OnchainCollector(Collector):
    name = "etherscan"  # tier-gates on the etherscan key; blockchair is always free

    def __init__(
        self,
        blockchair_chains: list[str] | None = None,
        etherscan_chain_ids: list[int] | None = None,
    ):
        self.blockchair_chains = blockchair_chains or DEFAULT_BLOCKCHAIR_CHAINS
        self.etherscan_chain_ids = etherscan_chain_ids or DEFAULT_ETHERSCAN_CHAIN_IDS

    def fetch(self, tier: str) -> Iterable[dict[str, Any]]:
        yield from self._fetch_blockchair()
        api_key = get_source("etherscan").active_key()
        if api_key:
            yield from self._fetch_etherscan(api_key)

    def _fetch_blockchair(self) -> Iterable[dict[str, Any]]:
        now = datetime.now(timezone.utc)
        for chain in self.blockchair_chains:
            resp = requests.get(f"{BLOCKCHAIR_BASE}/{chain}/stats", timeout=30)
            if resp.status_code != 200:
                continue
            data = resp.json().get("data", {})
            yield {
                "signal_type": "chain_stats",
                "entity": chain,
                "ts": now,
                "payload": data,
                "source": "blockchair",
                "tier": "free",
            }

    def _fetch_etherscan(self, api_key: str) -> Iterable[dict[str, Any]]:
        # TODO(untested, no key available): confirm module/action params and
        # response shape against https://api.etherscan.io/v2/api once
        # ETHERSCAN_API_KEY is set.
        now = datetime.now(timezone.utc)
        for chain_id in self.etherscan_chain_ids:
            resp = requests.get(
                ETHERSCAN_V2_BASE,
                params={
                    "chainid": chain_id,
                    "module": "stats",
                    "action": "ethsupply",
                    "apikey": api_key,
                },
                timeout=30,
            )
            if resp.status_code != 200:
                continue
            yield {
                "signal_type": "chain_supply",
                "entity": str(chain_id),
                "ts": now,
                "payload": resp.json(),
                "source": "etherscan",
                "tier": "free",
            }
