"""Tests for the Phase 4 walk-forward + significance harness (pure logic).

Covers the parts that don't need a running ``BacktestEngine``: stream slicing,
the threshold grid, the permutation shuffle, and the report aggregations. The
engine-driven ``run_window`` path is exercised by the CLI runs, not here.

Runs under pytest, or standalone: ``python tests/test_backtest_harness.py``.
"""

from __future__ import annotations

import os
import random
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from quiverquant.backtest.data import FearGreedData, TvlData  # noqa: E402
from quiverquant.backtest.harness import (  # noqa: E402
    WindowResult,
    slice_bars,
    slice_fg,
    slice_tvl,
)
from quiverquant.backtest.strategy import RegimeContrarianConfig  # noqa: E402
from quiverquant.backtest.significance import (  # noqa: E402
    SignificanceReport,
    _shuffle_values,
)
from quiverquant.backtest.walkforward import (  # noqa: E402
    Fold,
    WalkForwardReport,
    _param_grid,
    _param_label,
)


class _Bar:
    """Minimal stand-in — slice_bars only reads ts_event."""

    def __init__(self, ts_event: int) -> None:
        self.ts_event = ts_event


def _fg(ts: int, value: float, classification: str = "x") -> FearGreedData:
    return FearGreedData(ts_event=ts, ts_init=ts, value=value, classification=classification)


# --- slicing --------------------------------------------------------------

def test_slice_bars_is_half_open():
    bars = [_Bar(t) for t in (10, 20, 30, 40)]
    got = [b.ts_event for b in slice_bars(bars, 20, 40)]
    assert got == [20, 30]  # start inclusive, end exclusive


def test_slice_fg_is_half_open():
    fg = [_fg(10, 1), _fg(20, 2), _fg(30, 3)]
    got = [d.value for d in slice_fg(fg, 20, 100)]
    assert got == [2.0, 3.0]


def test_slice_empty_when_out_of_range():
    bars = [_Bar(10), _Bar(20)]
    assert slice_bars(bars, 100, 200) == []


def test_slice_tvl_is_half_open():
    tvl = [
        TvlData(ts_event=10, ts_init=10, total_usd=1.0, protocol_count=1),
        TvlData(ts_event=20, ts_init=20, total_usd=2.0, protocol_count=1),
        TvlData(ts_event=30, ts_init=30, total_usd=3.0, protocol_count=1),
    ]
    got = [d.total_usd for d in slice_tvl(tvl, 20, 30)]
    assert got == [2.0]  # start inclusive, end exclusive


# --- regime config --------------------------------------------------------

def test_regime_config_inherits_and_adds_window():
    cfg = RegimeContrarianConfig(instrument_id="BTCUSDT.BINANCE", bar_type="bt")
    assert cfg.fear_threshold == 30  # inherited default
    assert cfg.greed_threshold == 70
    assert cfg.tvl_ma_window == 30   # new default


# --- grid -----------------------------------------------------------------

def test_sentiment_grid_only_keeps_fear_below_greed():
    grid = _param_grid("sentiment", (20, 70), (30, 60), (8,))
    assert grid == [
        {"fear_threshold": 20, "greed_threshold": 30},
        {"fear_threshold": 20, "greed_threshold": 60},
    ]  # 70>30, 70>60 dropped


def test_dev_grid_is_over_ma_windows():
    grid = _param_grid("dev", (20,), (60,), (4, 8, 13))
    assert grid == [{"dev_ma_window": 4}, {"dev_ma_window": 8}, {"dev_ma_window": 13}]


def test_news_grid_only_keeps_low_below_high():
    grid = _param_grid("news", (20,), (60,), (8,), news_lows=(-0.1, 0.1), news_highs=(0.0, 0.2))
    # -0.1<0.0, -0.1<0.2, 0.1<0.2 kept; 0.1<0.0 dropped
    assert grid == [
        {"news_low": -0.1, "news_high": 0.0},
        {"news_low": -0.1, "news_high": 0.2},
        {"news_low": 0.1, "news_high": 0.2},
    ]


def test_default_grid_nonempty():
    from quiverquant.backtest.walkforward import (
        DEFAULT_DEV_WINDOWS,
        DEFAULT_FEARS,
        DEFAULT_GREEDS,
    )

    sg = _param_grid("sentiment", DEFAULT_FEARS, DEFAULT_GREEDS, DEFAULT_DEV_WINDOWS)
    dg = _param_grid("dev", DEFAULT_FEARS, DEFAULT_GREEDS, DEFAULT_DEV_WINDOWS)
    assert sg and all(p["fear_threshold"] < p["greed_threshold"] for p in sg)
    assert dg and all("dev_ma_window" in p for p in dg)


def test_param_label_renders_each_strategy():
    assert _param_label({"fear_threshold": 30, "greed_threshold": 70}) == "F30/G70"
    assert _param_label({"dev_ma_window": 8}) == "MA8w"
    assert _param_label({"news_low": -0.1, "news_high": 0.05}) == "L-0.1/H0.05"


# --- permutation shuffle --------------------------------------------------

def test_shuffle_preserves_timestamps_and_value_multiset():
    fg = [_fg(t, v) for t, v in [(1, 10), (2, 20), (3, 30), (4, 40)]]
    out = _shuffle_values(fg, random.Random(0))
    assert [d.ts_event for d in out] == [1, 2, 3, 4]  # timestamps unchanged
    assert sorted(d.value for d in out) == [10, 20, 30, 40]  # same values, reordered


def test_shuffle_keeps_value_with_its_label():
    fg = [_fg(1, 10, "fear"), _fg(2, 90, "greed")]
    out = _shuffle_values(fg, random.Random(1))
    for d in out:
        assert (d.value, d.classification) in {(10.0, "fear"), (90.0, "greed")}


def test_shuffle_is_deterministic_for_seed():
    fg = [_fg(t, t * 10) for t in range(1, 8)]
    a = [d.value for d in _shuffle_values(fg, random.Random(7))]
    b = [d.value for d in _shuffle_values(fg, random.Random(7))]
    assert a == b


# --- WindowResult ---------------------------------------------------------

def test_window_excess_pct():
    r = WindowResult(
        start_ns=0, end_ns=1, n_bars=5, fear_threshold=30, greed_threshold=70,
        entries=1, exits=1, net_worth=110_000.0,
        strategy_return_pct=10.0, buy_hold_return_pct=25.0,
    )
    assert r.excess_pct == -15.0


def test_window_excess_pct_none_when_missing():
    r = WindowResult(
        start_ns=0, end_ns=1, n_bars=0, fear_threshold=30, greed_threshold=70,
        entries=0, exits=0, net_worth=100_000.0,
        strategy_return_pct=0.0, buy_hold_return_pct=None,
    )
    assert r.excess_pct is None


# --- WalkForwardReport ----------------------------------------------------

def _fold(i: int, strat: float, bh: float) -> Fold:
    return Fold(
        index=i, train_bars=100, params={"fear_threshold": 30, "greed_threshold": 70},
        param_label="F30/G70", in_sample_excess_pct=1.0,
        test=WindowResult(
            start_ns=0, end_ns=1, n_bars=10, fear_threshold=30, greed_threshold=70,
            entries=1, exits=1, net_worth=0.0,
            strategy_return_pct=strat, buy_hold_return_pct=bh,
        ),
    )


def test_walkforward_aggregations():
    folds = [_fold(0, 10, 5), _fold(1, -5, 8), _fold(2, 20, 25)]
    rep = WalkForwardReport(n_splits=3, train_frac=0.4, folds=folds)
    assert rep.folds_positive == 2  # 10, 20 positive; -5 not
    assert rep.folds_beating_buyhold == 1  # only fold 0 (10>5)
    # compounded: 1.10 * 0.95 * 1.20 - 1 = 0.254
    assert rep.compounded_oos_pct == 25.4


def test_walkforward_compounded_none_when_empty():
    rep = WalkForwardReport(n_splits=0, train_frac=0.4, folds=[])
    assert rep.compounded_oos_pct is None


# --- SignificanceReport ---------------------------------------------------

def test_significance_pvalue_and_count():
    rep = SignificanceReport(
        actual_return_pct=46.0, n_permutations=9,
        permuted_returns=[50.0, 60.0, 10.0, 20.0, 30.0, 40.0, 45.0, 47.0, 5.0],
        seed=42,
    )
    assert rep.n_ge_actual == 3  # 50, 60, 47 >= 46
    # (3 + 1) / (9 + 1) = 0.4
    assert rep.p_value == 0.4


def test_significance_null_stats():
    rep = SignificanceReport(
        actual_return_pct=10.0, n_permutations=3,
        permuted_returns=[-5.0, 0.0, 25.0], seed=1,
    )
    assert rep.null_min_pct == -5.0
    assert rep.null_max_pct == 25.0
    assert rep.null_mean_pct == 6.67


def _run_standalone() -> int:
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    for fn in fns:
        try:
            fn()
            print(f"PASS {fn.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"FAIL {fn.__name__}: {e}")
    print(f"\n{len(fns) - failed}/{len(fns)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(_run_standalone())
