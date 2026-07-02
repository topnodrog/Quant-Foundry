"""Central settings and per-source tier resolution.

Each data source can run in a "free" tier (no key, or a free-signup key) or
a "paid" tier (higher rate limits / more history, requires a paid key). The
tier for a source is "paid" only if its paid-tier env var is set; otherwise
it falls back to "free". This lets Phase 1 run entirely on free tiers today
and upgrade individual sources later just by setting an env var.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
DB_PATH = DATA_DIR / "quiverquant.duckdb"


@dataclass(frozen=True)
class SourceKeys:
    """Env var names that gate a source's free/paid tier and hold credentials."""

    free_key_env: str | None = None
    paid_key_env: str | None = None

    def tier(self) -> str:
        if self.paid_key_env and os.getenv(self.paid_key_env):
            return "paid"
        return "free"

    def free_key(self) -> str | None:
        return os.getenv(self.free_key_env) if self.free_key_env else None

    def paid_key(self) -> str | None:
        return os.getenv(self.paid_key_env) if self.paid_key_env else None

    def active_key(self) -> str | None:
        return self.paid_key() if self.tier() == "paid" else self.free_key()


# One entry per PLAN.md §2 source, in priority order.
SOURCES: dict[str, SourceKeys] = {
    # TVL/protocols is free; token-unlock/emissions data is DefiLlama-paid-plan-only
    # as of 2026-07 (api.llama.fi/emissions returns 402 without a pro key) —
    # PLAN.md assumed unlocks were free, verified otherwise while building this.
    "defillama": SourceKeys(paid_key_env="DEFILLAMA_API_KEY"),
    "ccxt": SourceKeys(),  # no key, public market data
    "etherscan": SourceKeys(free_key_env="ETHERSCAN_API_KEY"),
    "blockchair": SourceKeys(free_key_env="BLOCKCHAIR_API_KEY"),
    "cryptopanic": SourceKeys(free_key_env="CRYPTOPANIC_API_KEY"),
    "electric_capital": SourceKeys(),  # public git repo, no key
    "github": SourceKeys(free_key_env="GITHUB_TOKEN"),
    "sec_edgar": SourceKeys(),  # no key, public
    "whale_alert": SourceKeys(free_key_env="WHALE_ALERT_SOURCE"),
    "nansen": SourceKeys(free_key_env="NANSEN_API_KEY", paid_key_env="NANSEN_PAID_API_KEY"),
    "dune": SourceKeys(free_key_env="DUNE_API_KEY", paid_key_env="DUNE_PAID_API_KEY"),
}


def get_source(name: str) -> SourceKeys:
    return SOURCES[name]
