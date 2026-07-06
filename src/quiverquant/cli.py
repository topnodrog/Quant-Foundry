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

    if argv and argv[0] == "walkforward":
        # Phase 4: anchored walk-forward validation (§6 step 2) — tune thresholds
        # in-sample, score out-of-sample, rolling forward.
        raise SystemExit(_walkforward_cli(argv[1:]))

    if argv and argv[0] == "significance":
        # Phase 4: permutation test (§6 step 3) — does the signal beat shuffled noise?
        raise SystemExit(_significance_cli(argv[1:]))

    if argv and argv[0] == "graph-features":
        # Lever #2: derived VC-conviction / co-investment features from the
        # FundBacksProtocol ontology edges (research/open-foundry-strategic-advantage.md).
        raise SystemExit(_graph_features_cli(argv[1:]))

    if argv and argv[0] == "resolve-tokens":
        # Path 1A: map VC-backed company names to tradeable CoinGecko tokens.
        raise SystemExit(_resolve_tokens_cli(argv[1:]))

    if argv and argv[0] == "collect-prices":
        # Path 1B: daily price history for the resolved tokens (CoinGecko).
        raise SystemExit(_collect_prices_cli(argv[1:]))

    if argv and argv[0] == "cross-section":
        # Path 1C: cross-sectional VC-conviction long book (survivorship-biased).
        raise SystemExit(_cross_section_cli(argv[1:]))

    if argv and argv[0] == "perigon-probe":
        # Spend ONE Perigon call to verify the key + measure history lookback.
        raise SystemExit(_perigon_probe_cli(argv[1:]))

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

    p_dev = sub.add_parser("dev-activity", help="weekly commit history per repo")
    p_dev.add_argument("--repos", nargs="*", help="explicit owner/repo list (default watchlist)")
    p_dev.add_argument("--since", help="only weeks on/after this UTC date, YYYY-MM-DD")

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

    if ns.source == "dev-activity":
        from quiverquant.backfill.github_dev import backfill_dev_activity

        since = (
            datetime.strptime(ns.since, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            if ns.since
            else None
        )
        total = backfill_dev_activity(repos=ns.repos, since=since)
        print(f"dev-activity: inserted {total} new repo-weeks")
        return 0

    return 1


def _backtest_cli(args: list[str]) -> int:
    import argparse

    from quiverquant.backtest.run import (
        print_strategy_summary,
        print_summary,
        run_backtest,
        run_sentiment_backtest,
    )

    parser = argparse.ArgumentParser(prog="quiverquant backtest")
    parser.add_argument(
        "--strategy",
        default="observer",
        choices=["observer", "sentiment", "regime"],
        help="observer = plumbing check; sentiment = Fear & Greed contrarian; "
             "regime = sentiment + TVL-momentum exit gate",
    )
    parser.add_argument("--exchange", default="binance")
    parser.add_argument("--symbol", default="BTC/USDT")
    parser.add_argument("--timeframe", help="default 1h for observer, 1d for sentiment/regime")
    parser.add_argument("--days", type=int, help="days of bars to backfill on cache miss")
    parser.add_argument("--tvl-ma-window", type=int, default=30, help="days for the TVL moving average (regime)")
    parser.add_argument("--balance", type=float, default=100_000.0)
    ns = parser.parse_args(args)

    if ns.strategy in ("sentiment", "regime"):
        summary = run_sentiment_backtest(
            exchange=ns.exchange,
            symbol=ns.symbol,
            timeframe=ns.timeframe or "1d",
            days=ns.days or 1460,
            starting_balance=ns.balance,
            strategy_name=ns.strategy,
            tvl_ma_window=ns.tvl_ma_window,
        )
        print_strategy_summary(summary)
        return 0

    summary = run_backtest(
        exchange=ns.exchange,
        symbol=ns.symbol,
        timeframe=ns.timeframe or "1h",
        days=ns.days or 35,
        starting_balance=ns.balance,
    )
    print_summary(summary)
    return 0


def _walkforward_cli(args: list[str]) -> int:
    import argparse

    from quiverquant.backtest.walkforward import print_report, walk_forward

    parser = argparse.ArgumentParser(prog="quiverquant walkforward")
    parser.add_argument("--strategy", default="sentiment", choices=["sentiment", "regime", "dev"],
                        help="sentiment = Fear & Greed only; regime = + TVL-momentum exit gate; "
                             "dev = developer-activity momentum")
    parser.add_argument("--exchange", default="binance")
    parser.add_argument("--symbol", default="BTC/USDT")
    parser.add_argument("--timeframe", default="1d")
    parser.add_argument("--days", type=int, default=1460, help="days of bars to backfill on cache miss")
    parser.add_argument("--splits", type=int, default=4, help="number of out-of-sample test windows")
    parser.add_argument("--train-frac", type=float, default=0.4, help="initial in-sample fraction")
    parser.add_argument("--tvl-ma-window", type=int, default=30, help="days for the TVL moving average (regime)")
    parser.add_argument("--balance", type=float, default=100_000.0)
    ns = parser.parse_args(args)

    report = walk_forward(
        strategy=ns.strategy,
        n_splits=ns.splits,
        train_frac=ns.train_frac,
        tvl_ma_window=ns.tvl_ma_window,
        starting_balance=ns.balance,
        exchange=ns.exchange,
        symbol=ns.symbol,
        timeframe=ns.timeframe,
        days=ns.days,
    )
    print_report(report)
    return 0


def _significance_cli(args: list[str]) -> int:
    import argparse

    from quiverquant.backtest.significance import permutation_test, print_report

    parser = argparse.ArgumentParser(prog="quiverquant significance")
    parser.add_argument("--strategy", default="sentiment", choices=["sentiment", "regime", "dev"],
                        help="sentiment = Fear & Greed only; regime = + TVL-momentum exit gate; "
                             "dev = developer-activity momentum")
    parser.add_argument("--exchange", default="binance")
    parser.add_argument("--symbol", default="BTC/USDT")
    parser.add_argument("--timeframe", default="1d")
    parser.add_argument("--days", type=int, default=1460, help="days of bars to backfill on cache miss")
    parser.add_argument("--permutations", type=int, default=100, help="number of shuffled-signal runs")
    parser.add_argument("--fear", type=int, default=30, help="fear entry threshold")
    parser.add_argument("--greed", type=int, default=70, help="greed exit threshold")
    parser.add_argument("--tvl-ma-window", type=int, default=30, help="days for the TVL moving average (regime)")
    parser.add_argument("--dev-ma-window", type=int, default=8, help="weeks for the dev-activity moving average (dev)")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--balance", type=float, default=100_000.0)
    ns = parser.parse_args(args)

    report = permutation_test(
        strategy=ns.strategy,
        n_permutations=ns.permutations,
        fear_threshold=ns.fear,
        greed_threshold=ns.greed,
        tvl_ma_window=ns.tvl_ma_window,
        dev_ma_window=ns.dev_ma_window,
        seed=ns.seed,
        starting_balance=ns.balance,
        exchange=ns.exchange,
        symbol=ns.symbol,
        timeframe=ns.timeframe,
        days=ns.days,
    )
    print_report(report)
    return 0


def _graph_features_cli(args: list[str]) -> int:
    import argparse

    from quiverquant.features.graph import compute_summary, print_summary, read_backings

    parser = argparse.ArgumentParser(prog="quiverquant graph-features")
    parser.add_argument("--min-funds", type=int, default=2,
                        help="min distinct backers for the conviction list")
    parser.add_argument("--limit", type=int, default=20, help="rows per section")
    ns = parser.parse_args(args)

    backings = read_backings()
    if not backings:
        print("no vc_portfolio_backing rows found — run `quiverquant firecrawl` first")
        return 1
    print_summary(compute_summary(backings, min_funds=ns.min_funds), limit=ns.limit)
    return 0


def _resolve_tokens_cli(args: list[str]) -> int:
    import argparse

    from quiverquant.features.token_resolve import build_map, distinct_companies, print_map

    parser = argparse.ArgumentParser(prog="quiverquant resolve-tokens")
    parser.add_argument("--top", type=int, default=1000,
                        help="size of the CoinGecko liquid universe to match against")
    ns = parser.parse_args(args)

    total = len(distinct_companies())
    resolutions = build_map(top_n=ns.top)
    print_map(resolutions, total_companies=total)
    print(f"\n  cached {len(resolutions)} rows to vc_token_map")
    return 0


def _collect_prices_cli(args: list[str]) -> int:
    import argparse

    from quiverquant.features.token_prices import collect_all, coverage_summary

    parser = argparse.ArgumentParser(prog="quiverquant collect-prices")
    parser.add_argument("--pause", type=float, default=6.0, help="seconds between CoinGecko calls")
    parser.add_argument("--days", default="max", help="history window (CoinGecko 'days' param)")
    ns = parser.parse_args(args)

    result = collect_all(pause=ns.pause, days=ns.days)
    total = sum(result.values())
    got = sum(1 for n in result.values() if n > 0)
    print(f"\ncollected {total} daily price rows across {got}/{len(result)} tokens")
    print("coverage (token / days / first / last):")
    for gid, n, first, last in coverage_summary():
        print(f"  {gid:28} {n:5}  {first}  {last}")
    return 0


def _cross_section_cli(args: list[str]) -> int:
    import argparse

    from quiverquant.features.cross_section import print_report, run_cross_section

    parser = argparse.ArgumentParser(prog="quiverquant cross-section")
    parser.add_argument("--min-funds", type=int, default=2, help="conviction threshold (distinct backers)")
    parser.add_argument("--permutations", type=int, default=500, help="random-subset null draws")
    parser.add_argument("--seed", type=int, default=42)
    ns = parser.parse_args(args)

    print_report(run_cross_section(
        min_funds=ns.min_funds, n_permutations=ns.permutations, seed=ns.seed
    ))
    return 0


def _perigon_probe_cli(args: list[str]) -> int:
    import argparse

    from quiverquant.collectors.perigon import PerigonError, print_probe, probe

    parser = argparse.ArgumentParser(prog="quiverquant perigon-probe")
    parser.add_argument("--q", default="bitcoin", help="test query term")
    parser.add_argument("--from", dest="frm", default="2022-01-01", help="lookback test window start")
    parser.add_argument("--to", default="2022-02-01", help="lookback test window end")
    ns = parser.parse_args(args)

    try:
        print_probe(probe(q=ns.q, test_from=ns.frm, test_to=ns.to))
    except PerigonError as e:
        print(f"perigon: {e}")
        return 1
    return 0


if __name__ == "__main__":
    main()
