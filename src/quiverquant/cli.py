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
from quiverquant.collectors.perigon import PerigonNewsCollector
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
    "perigon": PerigonNewsCollector,  # incremental crypto-news feed (1 call/run)
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

    if argv and argv[0] == "collect-universe":
        # Option 1: broad liquid-alt universe prices for cross-sectional momentum.
        raise SystemExit(_collect_universe_cli(argv[1:]))

    if argv and argv[0] == "momentum":
        # Option 1: cross-sectional momentum backtest (rank alts, long top-K).
        raise SystemExit(_momentum_cli(argv[1:]))

    if argv and argv[0] == "resolve-universe":
        # §9 step 2: resolve CMC snapshot members -> tickers (survivorship-free).
        raise SystemExit(_resolve_universe_cli(argv[1:]))

    if argv and argv[0] == "collect-pit-prices":
        # §9 step 2: price resolved members (Binance-archive-first for dead coins).
        raise SystemExit(_collect_pit_prices_cli(argv[1:]))

    if argv and argv[0] == "pit-momentum":
        # §9 step 2: survivorship-free cross-sectional momentum (candidate #6 re-run).
        raise SystemExit(_pit_momentum_cli(argv[1:]))

    if argv and argv[0] == "perigon-probe":
        # Spend ONE Perigon call to verify the key + measure history lookback.
        raise SystemExit(_perigon_probe_cli(argv[1:]))

    if argv and argv[0] == "wayback-vc":
        # Path 2: enumerate/probe Wayback snapshots of VC portfolio pages.
        raise SystemExit(_wayback_vc_cli(argv[1:]))

    if argv and argv[0] == "news-impact":
        # Perigon event study: BTC's biggest move days vs that day's crypto news.
        raise SystemExit(_news_impact_cli(argv[1:]))

    if argv and argv[0] == "news-backfill":
        # Backfill a monthly crypto-sentiment series for the Phase 4 gates.
        raise SystemExit(_news_backfill_cli(argv[1:]))

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

    p_cmc = sub.add_parser("cmc-snapshots", help="point-in-time top-200 universe membership (CoinMarketCap)")
    p_cmc.add_argument("--start", default="2018-01-01", help="first snapshot date, YYYY-MM-DD")
    p_cmc.add_argument("--end", help="last snapshot date, YYYY-MM-DD (default today)")
    p_cmc.add_argument("--step-days", type=int, default=30, help="days between snapshots")

    p_bv = sub.add_parser("binance-archive", help="delisted-pair daily klines (data.binance.vision)")
    p_bv.add_argument("--symbol", required=True, help="CCXT-style pair, e.g. BTCST/USDT")
    p_bv.add_argument("--start-year", type=int, default=2017)
    p_bv.add_argument("--start-month", type=int, default=1)

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

    if ns.source == "cmc-snapshots":
        from quiverquant.backfill.cmc_snapshots import backfill_snapshots, print_backfill_summary

        summary = backfill_snapshots(start=ns.start, end=ns.end, step_days=ns.step_days)
        print_backfill_summary(summary)
        return 0

    if ns.source == "binance-archive":
        from quiverquant.backfill.binance_vision import backfill_symbol, print_backfill_result

        added = backfill_symbol(ns.symbol, start_year=ns.start_year, start_month=ns.start_month)
        print_backfill_result(ns.symbol, added)
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
    parser.add_argument("--strategy", default="sentiment",
                        choices=["sentiment", "regime", "dev", "news", "ensemble"],
                        help="sentiment=Fear&Greed; regime=+TVL gate; dev=dev-activity; "
                             "news=news-sentiment; ensemble=consensus of all four")
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
    parser.add_argument("--strategy", default="sentiment",
                        choices=["sentiment", "regime", "dev", "news", "ensemble"],
                        help="sentiment=Fear&Greed; regime=+TVL gate; dev=dev-activity; "
                             "news=news-sentiment; ensemble=consensus of all four")
    parser.add_argument("--exchange", default="binance")
    parser.add_argument("--symbol", default="BTC/USDT")
    parser.add_argument("--timeframe", default="1d")
    parser.add_argument("--days", type=int, default=1460, help="days of bars to backfill on cache miss")
    parser.add_argument("--permutations", type=int, default=100, help="number of shuffled-signal runs")
    parser.add_argument("--fear", type=int, default=30, help="fear entry threshold")
    parser.add_argument("--greed", type=int, default=70, help="greed exit threshold")
    parser.add_argument("--tvl-ma-window", type=int, default=30, help="days for the TVL moving average (regime)")
    parser.add_argument("--dev-ma-window", type=int, default=8, help="weeks for the dev-activity moving average (dev)")
    parser.add_argument("--news-low", type=float, default=-0.10, help="net-sentiment capitulation entry (news)")
    parser.add_argument("--news-high", type=float, default=0.05, help="net-sentiment euphoria exit (news)")
    parser.add_argument("--min-votes", type=int, default=2, help="signals that must agree (ensemble)")
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
        news_low=ns.news_low,
        news_high=ns.news_high,
        min_votes=ns.min_votes,
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


def _collect_universe_cli(args: list[str]) -> int:
    import argparse

    from quiverquant.features.universe import collect_universe

    parser = argparse.ArgumentParser(prog="quiverquant collect-universe")
    parser.add_argument("--top", type=int, default=80, help="top-N coins by market cap to consider")
    parser.add_argument("--min-days", type=int, default=120, help="drop coins with less price history than this")
    parser.add_argument("--resume", action="store_true", help="keep existing members, only fetch missing coins")
    ns = parser.parse_args(args)

    s = collect_universe(top_n=ns.top, min_days=ns.min_days, resume=ns.resume)
    print(f"\nuniverse: {s['universe_size']} tradeable alts, {s['price_rows']} daily price rows")
    if s["skipped"]:
        print(f"skipped (not listed / too little history): {', '.join(s['skipped'])}")
    return 0


def _momentum_cli(args: list[str]) -> int:
    import argparse

    from quiverquant.features.momentum import print_report, run_momentum

    parser = argparse.ArgumentParser(prog="quiverquant momentum")
    parser.add_argument("--lookback", type=int, default=90, help="trailing days for the momentum rank")
    parser.add_argument("--hold", type=int, default=30, help="rebalance / holding period in days")
    parser.add_argument("--top-k", type=int, default=10, help="number of top-ranked coins to hold")
    parser.add_argument("--permutations", type=int, default=500, help="random-selection null draws")
    parser.add_argument("--seed", type=int, default=42)
    ns = parser.parse_args(args)

    print_report(run_momentum(
        lookback=ns.lookback, hold=ns.hold, top_k=ns.top_k,
        n_permutations=ns.permutations, seed=ns.seed,
    ))
    return 0


def _resolve_universe_cli(args: list[str]) -> int:
    import argparse

    from quiverquant.features.pit_universe import (
        print_resolution_summary, refresh_coingecko_list, resolve_symbols,
    )

    parser = argparse.ArgumentParser(prog="quiverquant resolve-universe")
    parser.add_argument("--refresh", action="store_true", help="refetch CoinGecko's full /coins/list first")
    parser.add_argument("--top", type=int, default=80, help="resolve members ever ranked <= this")
    ns = parser.parse_args(args)

    if ns.refresh:
        n = refresh_coingecko_list()
        print(f"cached {n} CoinGecko coins (incl. delisted)")
    print_resolution_summary(resolve_symbols(top_n=ns.top))
    return 0


def _collect_pit_prices_cli(args: list[str]) -> int:
    import argparse

    from quiverquant.features.pit_universe import (
        collect_prices, coverage_report, print_price_summary,
    )

    parser = argparse.ArgumentParser(prog="quiverquant collect-pit-prices")
    parser.add_argument("--top", type=int, default=80, help="price members ever ranked <= this")
    parser.add_argument("--limit", type=int, help="cap how many members to price this run")
    parser.add_argument("--fresh", action="store_true", help="re-price members already priced")
    ns = parser.parse_args(args)

    print_price_summary(collect_prices(top_n=ns.top, limit=ns.limit, resume=not ns.fresh))
    cov = coverage_report(top_n=ns.top)
    if cov.get("dates"):
        print(f"\n  priceable coverage: median {cov['median_priced_per_snapshot']} of top-{ns.top} "
              f"per snapshot, avg {cov['avg_coverage_pct']}%")
    return 0


def _pit_momentum_cli(args: list[str]) -> int:
    import argparse

    from quiverquant.features.pit_momentum import print_report, run_pit_momentum

    parser = argparse.ArgumentParser(prog="quiverquant pit-momentum")
    parser.add_argument("--lookback", type=int, default=90, help="trailing days for the momentum rank")
    parser.add_argument("--hold", type=int, default=30, help="rebalance / holding period in days")
    parser.add_argument("--top-k", type=int, default=10, help="number of top-ranked coins to hold")
    parser.add_argument("--top-n", type=int, default=80, help="universe = coins ranked <= this at each date")
    parser.add_argument("--fee-bps", type=float, default=10.0, help="one-way taker fee in bps (10 = 0.1%%)")
    parser.add_argument("--permutations", type=int, default=500, help="random-selection null draws")
    parser.add_argument("--seed", type=int, default=42)
    ns = parser.parse_args(args)

    print_report(run_pit_momentum(
        lookback=ns.lookback, hold=ns.hold, top_k=ns.top_k, top_n=ns.top_n,
        fee_bps=ns.fee_bps, n_permutations=ns.permutations, seed=ns.seed,
    ))
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


def _wayback_vc_cli(args: list[str]) -> int:
    import argparse

    from quiverquant.features.wayback_vc import (
        VC_PORTFOLIO_URLS,
        collect_point_in_time,
        fetch_snapshot,
        list_snapshots,
        probe_extractable,
    )

    parser = argparse.ArgumentParser(prog="quiverquant wayback-vc")
    parser.add_argument("--fund", default="a16z crypto", choices=list(VC_PORTFOLIO_URLS),
                        help="which VC portfolio page to enumerate")
    parser.add_argument("--from-year", type=int, default=2020)
    parser.add_argument("--to-year", type=int, default=2026)
    parser.add_argument("--probe", action="store_true",
                        help="also fetch one snapshot and check if companies are extractable")
    parser.add_argument("--extract", action="store_true",
                        help="walk all snapshots, extract companies, store point-in-time backings")
    parser.add_argument("--index", type=int, default=-1,
                        help="snapshot index to probe (default -1 = latest)")
    ns = parser.parse_args(args)

    if ns.extract:
        s = collect_point_in_time(ns.fund, from_year=ns.from_year, to_year=ns.to_year)
        print(f"\n=== Point-in-time VC portfolio: {s['fund']} ===")
        print(f"  snapshots: {s['snapshots_extractable']}/{s['snapshots_total']} extractable"
              f"  ({s.get('date_range', 'n/a')})")
        print(f"  distinct companies over time : {s['companies']}  (stored {s.get('rows_inserted', 0)} rows)")
        churned = s.get("churned_out", [])
        print(f"  churned OUT of portfolio (survivorship-bias fix): {len(churned)}")
        if churned:
            print(f"    {', '.join(churned[:30])}{' ...' if len(churned) > 30 else ''}")
        return 0

    url = VC_PORTFOLIO_URLS[ns.fund]
    snaps = list_snapshots(url, from_year=ns.from_year, to_year=ns.to_year)
    print(f"\n=== Wayback snapshots: {ns.fund} ({url}) ===")
    print(f"  {len(snaps)} monthly captures {ns.from_year}-{ns.to_year}")
    for s in snaps[:6]:
        print(f"    {s.date}  {s.raw_url}")
    if len(snaps) > 6:
        print(f"    ... and {len(snaps) - 6} more (last: {snaps[-1].date})")

    if ns.probe and snaps:
        snap = snaps[ns.index]
        print(f"\n  probing snapshot {snap.date} for extractable content ...")
        diag = probe_extractable(fetch_snapshot(snap))
        print(f"    html length          : {diag['html_len']}")
        print(f"    known companies found: {diag['n_known_found']}  {diag['known_companies_found']}")
        print(f"    embedded JSON payload: {diag['looks_like_spa_json']}")
        print(f"    verdict              : {diag['verdict']}")
    return 0


def _news_backfill_cli(args: list[str]) -> int:
    import argparse

    from quiverquant.collectors.perigon import PerigonError, backfill_monthly_sentiment

    parser = argparse.ArgumentParser(prog="quiverquant news-backfill")
    parser.add_argument("--start", default="2022-01", help="first month YYYY-MM (Perigon reaches 2022)")
    parser.add_argument("--end", default="2026-07", help="exclusive end month YYYY-MM")
    ns = parser.parse_args(args)

    try:
        n = backfill_monthly_sentiment(start=ns.start, end=ns.end)
        print(f"news-backfill: inserted {n} monthly sentiment points")
    except PerigonError as e:
        print(f"perigon: {e}")
        return 1
    return 0


def _news_impact_cli(args: list[str]) -> int:
    import argparse

    from quiverquant.collectors.perigon import PerigonError
    from quiverquant.features.news_impact import print_impact, run_news_impact

    parser = argparse.ArgumentParser(prog="quiverquant news-impact")
    parser.add_argument("--top", type=int, default=10,
                        help="how many of BTC's biggest move days to examine (= Perigon calls)")
    ns = parser.parse_args(args)

    try:
        print_impact(run_news_impact(n=ns.top))
    except PerigonError as e:
        print(f"perigon: {e}")
        return 1
    return 0


if __name__ == "__main__":
    main()
