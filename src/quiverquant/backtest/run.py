"""Wire the pieces into a ``BacktestEngine`` run and report data flow.

Phase 3 increment 1: this stands up a Binance BTC/USDT spot venue, feeds it
historical price bars (CCXT-sourced, DuckDB-cached) plus the Fear & Greed custom
data stream, runs the no-op ``ObserverStrategy``, and prints how much of each
stream was delivered and whether ordering held. No orders, no P&L — that's a
later increment.
"""

from __future__ import annotations

from datetime import datetime, timezone

from nautilus_trader.backtest.engine import BacktestEngine
from nautilus_trader.model.data import BarType, CustomData, DataType
from nautilus_trader.model.identifiers import ClientId
from nautilus_trader.model.enums import AccountType, OmsType
from nautilus_trader.model.objects import Money
from nautilus_trader.model.currencies import USDT
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

# CCXT timeframe -> nautilus BarSpecification token
_BAR_SPEC = {"1h": "1-HOUR", "4h": "4-HOUR", "1d": "1-DAY"}

_SIGNAL_TYPE = "fear_greed_index"

# Custom (non-instrument) data needs a client id so the engine can route it.
_CLIENT_ID = ClientId("QUIVERQUANT")


def _ns_to_iso(ns: int | None) -> str | None:
    if ns is None:
        return None
    return datetime.fromtimestamp(ns / 1_000_000_000, tz=timezone.utc).isoformat()


def run_backtest(
    exchange: str = "binance",
    symbol: str = "BTC/USDT",
    timeframe: str = "1h",
    days: int = 35,
    starting_balance: float = 100_000.0,
) -> dict:
    """Run the plumbing backtest. Returns a summary dict (also printed by the CLI)."""
    if timeframe not in _BAR_SPEC:
        raise ValueError(f"Unsupported timeframe {timeframe!r}; supported: {list(_BAR_SPEC)}")

    # --- price bars: read cache, backfill on miss --------------------------------
    df = read_ohlcv_df(exchange, symbol, timeframe)
    if df.empty:
        cached = backfill(exchange, symbol, timeframe, days=days)
        print(f"[ohlcv] cache miss -> backfilled {cached} bars for {symbol} {timeframe}")
        df = read_ohlcv_df(exchange, symbol, timeframe)

    # --- instrument + venue ------------------------------------------------------
    instrument = TestInstrumentProvider.btcusdt_binance()
    bar_type = BarType.from_str(f"{instrument.id}-{_BAR_SPEC[timeframe]}-LAST-EXTERNAL")

    engine = BacktestEngine()
    engine.add_venue(
        venue=instrument.venue,
        oms_type=OmsType.NETTING,
        account_type=AccountType.CASH,
        starting_balances=[Money(starting_balance, USDT)],
    )
    engine.add_instrument(instrument)

    # --- data: price bars + Fear & Greed custom stream ---------------------------
    bars = build_bars(instrument, bar_type, df)
    engine.add_data(bars)

    points = read_signal_points(_SIGNAL_TYPE)
    fg = build_fear_greed_data(points)
    if fg:
        # Custom data must be delivered wrapped in a CustomData envelope; the
        # engine unwraps it and publishes the inner FearGreedData to subscribers.
        fg_type = DataType(FearGreedData)
        engine.add_data([CustomData(fg_type, d) for d in fg], client_id=_CLIENT_ID)

    tvl = build_tvl_data(read_daily_tvl_total())
    if tvl:
        tvl_type = DataType(TvlData)
        engine.add_data([CustomData(tvl_type, d) for d in tvl], client_id=_CLIENT_ID)

    # --- strategy ----------------------------------------------------------------
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
