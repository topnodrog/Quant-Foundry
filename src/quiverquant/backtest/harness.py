"""Phase 4 harness core — run one strategy over a *bounded slice* of data.

The Phase 3 ``run.py`` runs a single backtest over the whole history. Walk-forward
validation (§6 step 2) and the statistical-significance check (§6 step 3) both
need to run the *same* strategy many times over different windows (and, for
significance, over shuffled signals). This module is that shared primitive:

- ``load_dataset``  — load price bars + the Fear & Greed series once, so callers
  slice in memory instead of re-hitting DuckDB/CCXT per run.
- ``slice_bars`` / ``slice_fg`` — cut a stream to a ``[start_ns, end_ns)`` window
  by event time (nautilus nanoseconds).
- ``run_window`` — build a fresh, log-silenced ``BacktestEngine`` over a given
  bar/Fear-&-Greed slice, run the Fear & Greed contrarian strategy, and return a
  ``WindowResult`` with the honest net-worth return plus a buy-&-hold benchmark
  over the *same* window.

Every run uses the same realistic fee/fill models as the Phase 3 strategy backtest
(Binance 0.1% maker/taker + probabilistic slippage) so results are comparable.
Fill randomness is pinned to a fixed seed so the only thing that varies between a
walk-forward fold or a permutation draw is the *data*, not the fill dice.
"""

from __future__ import annotations

from dataclasses import dataclass

from nautilus_trader.backtest.engine import BacktestEngine
from nautilus_trader.backtest.models import FillModel, MakerTakerFeeModel
from nautilus_trader.config import BacktestEngineConfig, LoggingConfig
from nautilus_trader.model.data import BarType, CustomData, DataType
from nautilus_trader.model.identifiers import ClientId
from nautilus_trader.model.enums import AccountType, OmsType
from nautilus_trader.model.objects import Money
from nautilus_trader.model.currencies import BTC, USDT
from nautilus_trader.test_kit.providers import TestInstrumentProvider

from quiverquant.backtest.data import (
    DevActivityData,
    FearGreedData,
    TvlData,
    build_bars,
    build_dev_data,
    build_fear_greed_data,
    build_tvl_data,
)
from quiverquant.backtest.ohlcv import backfill, read_ohlcv_df
from quiverquant.backtest.signals import (
    read_daily_tvl_total,
    read_signal_points,
    read_weekly_dev_total,
)
from quiverquant.backtest.strategy import (
    DevMomentumConfig,
    DevMomentumStrategy,
    FearGreedContrarianConfig,
    FearGreedContrarianStrategy,
    RegimeContrarianConfig,
    RegimeContrarianStrategy,
)

_BAR_SPEC = {"1h": "1-HOUR", "4h": "4-HOUR", "1d": "1-DAY"}
_SIGNAL_TYPE = "fear_greed_index"
_CLIENT_ID = ClientId("QUIVERQUANT")
_FILL_SEED = 13  # fixed so fills don't add noise across walk-forward/permutation runs


@dataclass(frozen=True)
class Dataset:
    """Everything a run needs, loaded once and sliced in memory."""

    instrument: object
    bar_type: BarType
    bars: list  # list[Bar], ascending ts_event
    fg: list[FearGreedData]  # ascending ts_event
    tvl: list[TvlData]  # aggregate DeFi TVL, ascending ts_event
    dev: list[DevActivityData]  # market-wide weekly dev activity, ascending ts_event


@dataclass(frozen=True)
class WindowResult:
    """Outcome of one strategy run over one window."""

    start_ns: int | None
    end_ns: int | None
    n_bars: int
    fear_threshold: int
    greed_threshold: int
    entries: int
    exits: int
    net_worth: float
    strategy_return_pct: float | None
    buy_hold_return_pct: float | None

    @property
    def excess_pct(self) -> float | None:
        """Strategy return minus buy-&-hold over the same window."""
        if self.strategy_return_pct is None or self.buy_hold_return_pct is None:
            return None
        return round(self.strategy_return_pct - self.buy_hold_return_pct, 2)


def load_dataset(
    exchange: str = "binance",
    symbol: str = "BTC/USDT",
    timeframe: str = "1d",
    days: int = 1460,
) -> Dataset:
    """Load price bars + the Fear & Greed series once. Backfills bars on cache miss."""
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
    dev = build_dev_data(read_weekly_dev_total())
    return Dataset(
        instrument=instrument, bar_type=bar_type, bars=bars, fg=fg, tvl=tvl, dev=dev
    )


def time_bounds(bars: list) -> tuple[int, int]:
    """(first_ts_event, last_ts_event + 1) for a non-empty ascending bar list."""
    if not bars:
        raise ValueError("no bars")
    return bars[0].ts_event, bars[-1].ts_event + 1


def slice_bars(bars: list, start_ns: int, end_ns: int) -> list:
    """Bars whose ``ts_event`` falls in ``[start_ns, end_ns)``."""
    return [b for b in bars if start_ns <= b.ts_event < end_ns]


def slice_fg(fg: list[FearGreedData], start_ns: int, end_ns: int) -> list[FearGreedData]:
    """Fear & Greed points whose ``ts_event`` falls in ``[start_ns, end_ns)``."""
    return [d for d in fg if start_ns <= d.ts_event < end_ns]


def slice_tvl(tvl: list[TvlData], start_ns: int, end_ns: int) -> list[TvlData]:
    """Aggregate-TVL points whose ``ts_event`` falls in ``[start_ns, end_ns)``."""
    return [d for d in tvl if start_ns <= d.ts_event < end_ns]


def slice_dev(dev: list[DevActivityData], start_ns: int, end_ns: int) -> list[DevActivityData]:
    """Dev-activity points whose ``ts_event`` falls in ``[start_ns, end_ns)``."""
    return [d for d in dev if start_ns <= d.ts_event < end_ns]


def _make_engine() -> BacktestEngine:
    """A backtest engine with logging fully bypassed — walk-forward/significance
    spin up hundreds of these, so per-run log I/O would dominate runtime."""
    config = BacktestEngineConfig(logging=LoggingConfig(bypass_logging=True))
    return BacktestEngine(config=config)


def _build_strategy(
    name: str, instrument, bar_type, *,
    fear_threshold, greed_threshold, tvl_ma_window, dev_ma_window,
):
    """Construct the requested strategy. ``sentiment`` = Fear & Greed contrarian;
    ``regime`` = the same plus a DeFi-TVL momentum exit gate; ``dev`` =
    developer-activity momentum (long while builder activity is above its MA)."""
    if name == "regime":
        return RegimeContrarianStrategy(
            RegimeContrarianConfig(
                instrument_id=instrument.id,
                bar_type=bar_type,
                fear_threshold=fear_threshold,
                greed_threshold=greed_threshold,
                tvl_ma_window=tvl_ma_window,
            )
        )
    if name == "dev":
        return DevMomentumStrategy(
            DevMomentumConfig(
                instrument_id=instrument.id,
                bar_type=bar_type,
                dev_ma_window=dev_ma_window,
            )
        )
    if name == "sentiment":
        return FearGreedContrarianStrategy(
            FearGreedContrarianConfig(
                instrument_id=instrument.id,
                bar_type=bar_type,
                fear_threshold=fear_threshold,
                greed_threshold=greed_threshold,
            )
        )
    raise ValueError(f"unknown strategy {name!r}; expected 'sentiment', 'regime' or 'dev'")


def run_window(
    dataset: Dataset,
    bars: list,
    fg: list[FearGreedData],
    tvl: list[TvlData] | None = None,
    dev: list[DevActivityData] | None = None,
    *,
    strategy: str = "sentiment",
    fear_threshold: int = 30,
    greed_threshold: int = 70,
    tvl_ma_window: int = 30,
    dev_ma_window: int = 8,
    starting_balance: float = 100_000.0,
) -> WindowResult:
    """Run a strategy over one bar/signal slice.

    ``strategy`` selects ``sentiment`` (Fear & Greed only), ``regime`` (adds a
    TVL-momentum exit gate — needs ``tvl``), or ``dev`` (developer-activity
    momentum — needs ``dev``). Reports ending NET WORTH (USDT + BTC*last_close),
    not the raw USDT bucket: on a CASH spot account an open position at window end
    splits value across currency buckets, so only the sum is an honest
    single-number return (same reasoning as ``run.run_sentiment_backtest``).
    """
    instrument = dataset.instrument
    if not bars:
        return WindowResult(
            start_ns=None, end_ns=None, n_bars=0,
            fear_threshold=fear_threshold, greed_threshold=greed_threshold,
            entries=0, exits=0, net_worth=starting_balance,
            strategy_return_pct=0.0, buy_hold_return_pct=None,
        )

    engine = _make_engine()
    engine.add_venue(
        venue=instrument.venue,
        oms_type=OmsType.NETTING,
        account_type=AccountType.CASH,
        starting_balances=[Money(starting_balance, USDT)],
        fee_model=MakerTakerFeeModel(),
        fill_model=FillModel(prob_slippage=0.2, random_seed=_FILL_SEED),
    )
    engine.add_instrument(instrument)
    engine.add_data(bars)
    if fg:
        engine.add_data(
            [CustomData(DataType(FearGreedData), d) for d in fg], client_id=_CLIENT_ID
        )
    if tvl:
        engine.add_data(
            [CustomData(DataType(TvlData), d) for d in tvl], client_id=_CLIENT_ID
        )
    if dev:
        engine.add_data(
            [CustomData(DataType(DevActivityData), d) for d in dev], client_id=_CLIENT_ID
        )

    strat = _build_strategy(
        strategy, instrument, dataset.bar_type,
        fear_threshold=fear_threshold, greed_threshold=greed_threshold,
        tvl_ma_window=tvl_ma_window, dev_ma_window=dev_ma_window,
    )
    engine.add_strategy(strat)
    engine.run()

    last_close = float(bars[-1].close)
    account = engine.portfolio.account(instrument.venue)
    usdt_bal = account.balance_total(USDT)
    btc_bal = account.balance_total(BTC)
    final_usdt = usdt_bal.as_double() if usdt_bal else 0.0
    final_btc = btc_bal.as_double() if btc_bal else 0.0
    net_worth = final_usdt + final_btc * last_close
    strategy_pct = round((net_worth / starting_balance - 1) * 100, 2) if starting_balance else None

    first_close = float(bars[0].close)
    buy_hold_pct = round((last_close / first_close - 1) * 100, 2) if first_close else None

    result = WindowResult(
        start_ns=bars[0].ts_event,
        end_ns=bars[-1].ts_event,
        n_bars=len(bars),
        fear_threshold=fear_threshold,
        greed_threshold=greed_threshold,
        entries=strat.entries,
        exits=strat.exits,
        net_worth=round(net_worth, 2),
        strategy_return_pct=strategy_pct,
        buy_hold_return_pct=buy_hold_pct,
    )
    engine.dispose()
    return result
