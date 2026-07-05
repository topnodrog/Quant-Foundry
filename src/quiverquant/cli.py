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

    if argv and argv[0] == "backfill":
        # Phase 3 prep: pull full history for sources that expose it, so
        # point-in-time collectors become backtestable time series.
        raise SystemExit(_backfill_cli(argv[1:]))

    requested = argv or list(COLLECTORS.keys())
    for key in requested:
        cls = COLLECTORS.get(key)
        if cls is None:
            print(f"unknown collector: {key} (available: {', '.join(COLLECTORS)})")
            continue
        n = cls().run()
        print(f"{key}: inserted {n} rows")


def _backfill_cli(args: list[str]) -> int:
    import argparse
    from datetime import datetime, timezone

    parser = argparse.ArgumentParser(prog="quiverquant backfill")
    sub = parser.add_subparsers(dest="source", required=True)

    p_fg = sub.add_parser("fear-greed", help="full Crypto Fear & Greed history")  # noqa: F841

    p_tvl = sub.add_parser("defillama-tvl", help="daily TVL history per top protocol")
    p_tvl.add_argument("--top", type=int, default=25, help="top-N protocols by TVL")
    p_tvl.add_argument("--slugs", nargs="*", help="explicit protocol slugs (overrides --top)")
    p_tvl.add_argument("--since", help="only points on/after this UTC date, YYYY-MM-DD")

    ns = parser.parse_args(args)

    if ns.source == "fear-greed":
        # limit=0 asks Alternative.me for the full history; the collector already
        # dedupes on the reading's date, so this is safe to re-run.
        from quiverquant.collectors.fear_greed import FearGreedCollector

        n = FearGreedCollector(limit=0).run()
        print(f"fear-greed: inserted {n} new daily readings")
        return 0

    if ns.source == "defillama-tvl":
        from quiverquant.backfill.defillama_tvl import backfill_tvl_history

        since = (
            datetime.strptime(ns.since, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            if ns.since
            else None
        )
        total = backfill_tvl_history(top=ns.top, slugs=ns.slugs, since=since)
        print(f"defillama-tvl: inserted {total} new TVL points")
        return 0

    return 1


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
