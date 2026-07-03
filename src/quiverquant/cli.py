"""Run one or all collectors: `uv run quiverquant [source ...]`."""

from __future__ import annotations

import sys

from quiverquant.collectors.ccxt_collector import CCXTCollector
from quiverquant.collectors.cryptopanic import CryptoPanicCollector
from quiverquant.collectors.defillama import DefiLlamaCollector
from quiverquant.collectors.dev_activity import DevActivityCollector
from quiverquant.collectors.fear_greed import FearGreedCollector
from quiverquant.collectors.onchain import OnchainCollector
from quiverquant.collectors.sec_edgar import SecEdgarCollector
from quiverquant.collectors.smart_money import SmartMoneyCollector
from quiverquant.collectors.whale_alert import WhaleAlertCollector

COLLECTORS = {
    "defillama": DefiLlamaCollector,
    "ccxt": CCXTCollector,
    "onchain": OnchainCollector,
    "cryptopanic": CryptoPanicCollector,
    "fear_greed": FearGreedCollector,
    "github": DevActivityCollector,
    "sec_edgar": SecEdgarCollector,
    "whale_alert": WhaleAlertCollector,
    "dune": SmartMoneyCollector,
}


def main() -> None:
    requested = sys.argv[1:] or list(COLLECTORS.keys())
    for key in requested:
        cls = COLLECTORS.get(key)
        if cls is None:
            print(f"unknown collector: {key} (available: {', '.join(COLLECTORS)})")
            continue
        n = cls().run()
        print(f"{key}: inserted {n} rows")


if __name__ == "__main__":
    main()
