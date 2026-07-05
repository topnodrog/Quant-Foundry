"""Run one or all collectors: `uv run quiverquant [source ...]`."""

from __future__ import annotations

import sys

from quiverquant.collectors.ccxt_collector import CCXTCollector
from quiverquant.collectors.cryptopanic import CryptoPanicCollector
from quiverquant.collectors.defillama import DefiLlamaCollector
from quiverquant.collectors.dev_activity import DevActivityCollector
from quiverquant.collectors.fear_greed import FearGreedCollector
from quiverquant.collectors.firecrawl_vc import FirecrawlVCCollector
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
    "firecrawl": FirecrawlVCCollector,
}


def main() -> None:
    argv = sys.argv[1:]
    if argv and argv[0] == "migrate-ontology":
        # Phase 2: migrate raw_signals into the Open Foundry crypto ontology.
        from quiverquant.ontology.migrate import main as migrate_main

        raise SystemExit(migrate_main(argv[1:]))

    if argv and argv[0] == "backtest":
        # Phase 3: plumbing backtest — feed price bars + Fear & Greed into
        # nautilus_trader's BacktestEngine and report data flow.
        raise SystemExit(_backtest_cli(argv[1:]))

    requested = argv or list(COLLECTORS.keys())
    for key in requested:
        cls = COLLECTORS.get(key)
        if cls is None:
            print(f"unknown collector: {key} (available: {', '.join(COLLECTORS)})")
            continue
        n = cls().run()
        print(f"{key}: inserted {n} rows")


def _backtest_cli(args: list[str]) -> int:
    import argparse

    from quiverquant.backtest.run import print_summary, run_backtest

    parser = argparse.ArgumentParser(prog="quiverquant backtest")
    parser.add_argument("--exchange", default="binance")
    parser.add_argument("--symbol", default="BTC/USDT")
    parser.add_argument("--timeframe", default="1h", choices=["1h", "4h", "1d"])
    parser.add_argument("--days", type=int, default=35, help="days of bars to backfill on cache miss")
    parser.add_argument("--balance", type=float, default=100_000.0)
    ns = parser.parse_args(args)

    summary = run_backtest(
        exchange=ns.exchange,
        symbol=ns.symbol,
        timeframe=ns.timeframe,
        days=ns.days,
        starting_balance=ns.balance,
    )
    print_summary(summary)
    return 0


if __name__ == "__main__":
    main()
