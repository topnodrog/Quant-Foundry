"""Wire the pieces into a ``BacktestEngine`` run and report results.

Two entry points over the same Binance BTC/USDT spot venue and data (price bars
+ Fear & Greed + aggregate DeFi TVL, all CCXT/DuckDB-sourced):

- ``run_backtest`` — the plumbing check: a no-op observer confirms every stream
  is delivered in event-time order.
- ``run_sentiment_backtest`` — the first real strategy (Fear & Greed contrarian)
  with Binance 0.1% maker/taker fees and probabilistic slippage, reporting
  PnL/return stats plus a buy-&-hold benchmark.
"""

from __future__ import annotations

from datetime import datetime, timezone

from nautilus_trader.backtest.engine import BacktestEngine
from nautilus_trader.backtest.models import FillModel, MakerTakerFeeModel
from nautilus_trader.model.data import BarType, CustomData, DataType
from nautilus_trader.model.identifiers import ClientId
from nautilus_trader.model.enums import AccountType, OmsType
from nautilus_trader.model.objects import Money
from nautilus_trader.model.currencies import BTC, USDT
from nautilus_trader.test_kit.providers import TestInstrumentProvider

from quiverquant.backtest.data import (
    FearGreedData,
    TvlData,
    build_bars,
    build_fear_greed_data,
    build_tvl_data,
)
from quiverquant.backtest.observer import ObserverConfig, ObserverStrategy
from quiverquant.backtest.ohlcv import backfill, read_ohlcv_df
from quiverquant.backtest.signals import read_daily_tvl_total, read_signal_points
from quiverquant.backtest.strategy import (
    FearGreedContrarianConfig,
    FearGreedContrarianStrategy,
    RegimeContrarianConfig,
    RegimeContrarianStrategy,
)

# CCXT timeframe -> nautilus BarSpecification token
_BAR_SPEC = {"1h": "1-HOUR", "4h": "4-HOUR", "1d": "1-DAY"}

_SIGNAL_TYPE = "fear_greed_index"

# Custom (non-instrument) data needs a client id so the engine can route it.
_CLIENT_ID = ClientId("QUIVERQUANT")


def _ns_to_iso(ns: int | None) -> str | None:
    if ns is None:
        return None
    return datetime.fromtimestamp(ns / 1_000_000_000, tz=timezone.utc).isoformat()


def _prepare_data(exchange: str, symbol: str, timeframe: str, days: int):
    """Load price bars + Fear & Greed + aggregate TVL. Backfills bars on cache
    miss. Returns (instrument, bar_type, bars, fg, tvl)."""
    if timeframe not in _BAR_SPEC:
        raise ValueError(f"Unsupported timeframe {timeframe!r}; supported: {list(_BAR_SPEC)}")

    df = read_ohlcv_df(exchange, symbol, timeframe)
    if df.empty:
        cached = backfill(exchange, symbol, timeframe, days=days)
        print(f"[ohlcv] cache miss -> backfilled {cached} bars for {symbol} {timeframe}")
        df = read_ohlcv_df(exchange, symbol, timeframe)

    instrument = TestInstrumentProvider.btcusdt_binance()
    bar_type = BarType.from_str(f"{instrument.id}-{_BAR_SPEC[timeframe]}-LAST-EXTERNAL")
    bars = build_bars(instrument, bar_type, df)
    fg = build_fear_greed_data(read_signal_points(_SIGNAL_TYPE))
    tvl = build_tvl_data(read_daily_tvl_total())
    return instrument, bar_type, bars, fg, tvl


def _add_data(engine: BacktestEngine, bars, fg, tvl) -> None:
    """Add price bars + custom-data streams to an engine (CustomData-wrapped)."""
    engine.add_data(bars)
    if fg:
        engine.add_data([CustomData(DataType(FearGreedData), d) for d in fg], client_id=_CLIENT_ID)
    if tvl:
        engine.add_data([CustomData(DataType(TvlData), d) for d in tvl], client_id=_CLIENT_ID)


def run_backtest(
    exchange: str = "binance",
    symbol: str = "BTC/USDT",
    timeframe: str = "1h",
    days: int = 35,
    starting_balance: float = 100_000.0,
) -> dict:
    """Run the plumbing backtest (no-op observer). Returns a delivery summary."""
    instrument, bar_type, bars, fg, tvl = _prepare_data(exchange, symbol, timeframe, days)

    engine = BacktestEngine()
    engine.add_venue(
        venue=instrument.venue,
        oms_type=OmsType.NETTING,
        account_type=AccountType.CASH,
        starting_balances=[Money(starting_balance, USDT)],
    )
    engine.add_instrument(instrument)
    _add_data(engine, bars, fg, tvl)

    strategy = ObserverStrategy(ObserverConfig(instrument_id=instrument.id, bar_type=bar_type))
    engine.add_strategy(strategy)
    engine.run()

    summary = {
        "instrument": str(instrument.id),
        "timeframe": timeframe,
        "bars_loaded": len(bars),
        "bars_delivered": strategy.bar_count,
        "fear_greed_loaded": len(fg),
        "fear_greed_delivered": strategy.signal_count,
        "tvl_loaded": len(tvl),
        "tvl_delivered": strategy.tvl_count,
        "first_event": _ns_to_iso(strategy.first_ts_event),
        "last_event": _ns_to_iso(strategy.last_ts_event),
        "out_of_order_events": strategy.out_of_order,
    }
    engine.dispose()
    return summary


def run_sentiment_backtest(
    exchange: str = "binance",
    symbol: str = "BTC/USDT",
    timeframe: str = "1d",
    days: int = 1460,
    starting_balance: float = 100_000.0,
    fear_threshold: int = 30,
    greed_threshold: int = 70,
    strategy_name: str = "sentiment",
    tvl_ma_window: int = 30,
) -> dict:
    """Run a contrarian strategy with realistic fees (Binance maker/taker 0.1%)
    and probabilistic slippage. ``strategy_name`` selects ``sentiment`` (Fear &
    Greed only) or ``regime`` (adds a TVL-momentum exit gate). Returns a
    performance summary including a buy-&-hold benchmark over the same window.
    """
    instrument, bar_type, bars, fg, tvl = _prepare_data(exchange, symbol, timeframe, days)

    engine = BacktestEngine()
    engine.add_venue(
        venue=instrument.venue,
        oms_type=OmsType.NETTING,
        account_type=AccountType.CASH,
        starting_balances=[Money(starting_balance, USDT)],
        fee_model=MakerTakerFeeModel(),  # uses the instrument's 0.1% maker/taker
        fill_model=FillModel(prob_slippage=0.2, random_seed=13),
    )
    engine.add_instrument(instrument)
    _add_data(engine, bars, fg, tvl)

    if strategy_name == "regime":
        strategy = RegimeContrarianStrategy(
            RegimeContrarianConfig(
                instrument_id=instrument.id,
                bar_type=bar_type,
                fear_threshold=fear_threshold,
                greed_threshold=greed_threshold,
                tvl_ma_window=tvl_ma_window,
            )
        )
    else:
        strategy = FearGreedContrarianStrategy(
            FearGreedContrarianConfig(
                instrument_id=instrument.id,
                bar_type=bar_type,
                fear_threshold=fear_threshold,
                greed_threshold=greed_threshold,
            )
        )
    engine.add_strategy(strategy)
    engine.run()

    result = engine.get_result()
    last_close = float(bars[-1].close) if bars else 0.0

    # True performance = ending NET WORTH, not the raw USDT bucket. On a CASH
    # spot account an open BTC position at the end leaves the cash it cost in the
    # USDT PnL bucket and the BTC it bought in the BTC bucket; only summing
    # USDT + BTC*last_price gives an honest single-number return.
    account = engine.portfolio.account(instrument.venue)
    usdt_bal = account.balance_total(USDT)
    btc_bal = account.balance_total(BTC)
    final_usdt = usdt_bal.as_double() if usdt_bal else 0.0
    final_btc = btc_bal.as_double() if btc_bal else 0.0
    net_worth = final_usdt + final_btc * last_close
    strategy_pct = round((net_worth / starting_balance - 1) * 100, 2) if starting_balance else None

    buy_hold_pct = None
    if bars:
        first_close = float(bars[0].close)
        if first_close:
            buy_hold_pct = round((last_close / first_close - 1) * 100, 2)

    summary = {
        "instrument": str(instrument.id),
        "timeframe": timeframe,
        "backtest_start": _ns_to_iso(int(result.backtest_start)) if result.backtest_start else None,
        "backtest_end": _ns_to_iso(int(result.backtest_end)) if result.backtest_end else None,
        "bars": len(bars),
        "fear_greed_points": len(fg),
        "thresholds": f"fear<={fear_threshold} / greed>={greed_threshold}",
        "entries": strategy.entries,
        "exits": strategy.exits,
        "total_orders": result.total_orders,
        "starting_balance_usdt": round(starting_balance, 2),
        "final_usdt": round(final_usdt, 2),
        "final_btc": round(final_btc, 6),
        "final_net_worth_usdt": round(net_worth, 2),
        "strategy_return_pct": strategy_pct,
        "buy_hold_return_pct": buy_hold_pct,
        "stats_returns": result.stats_returns,
    }
    engine.dispose()
    return summary


def print_summary(summary: dict) -> None:
    print("\n=== Phase 3 plumbing backtest ===")
    for k, v in summary.items():
        print(f"  {k:22} {v}")
    ok = (
        summary["bars_delivered"] == summary["bars_loaded"]
        and summary["fear_greed_delivered"] == summary["fear_greed_loaded"]
        and summary["tvl_delivered"] == summary["tvl_loaded"]
        and summary["out_of_order_events"] == 0
    )
    print(f"\n  plumbing {'OK - all streams delivered in order' if ok else 'PROBLEM - see counts above'}")


def print_strategy_summary(summary: dict) -> None:
    print("\n=== Fear & Greed contrarian strategy ===")
    for k, v in summary.items():
        if k == "stats_returns":
            continue
        print(f"  {k:24} {v}")
    stats = summary.get("stats_returns") or {}
    print("  stats_returns:")
    for name, val in stats.items():
        print(f"    {name:32} {val}")
    sp, bh = summary.get("strategy_return_pct"), summary.get("buy_hold_return_pct")
    if sp is not None and bh is not None:
        verdict = "beat" if sp > bh else "trailed"
        print(f"\n  strategy {sp}% vs buy&hold {bh}%  ->  {verdict} buy&hold")
