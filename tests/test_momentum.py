"""Tests for the cross-sectional momentum math (pure, synthetic — no network).

Runs under pytest, or standalone: ``python tests/test_momentum.py``.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pandas as pd  # noqa: E402

from quiverquant.features.momentum import (  # noqa: E402
    MomentumReport,
    book_total_return,
    qualifying,
    rebalance_windows,
    window_return,
)


def _prices(rows: int = 12) -> pd.DataFrame:
    idx = pd.date_range("2026-01-01", periods=rows, freq="D", tz="UTC")
    # A trends up (10..21), B flat at 5, C trends down (12..1)
    return pd.DataFrame(
        {
            "A": [10 + i for i in range(rows)],
            "B": [5.0] * rows,
            "C": [12 - i for i in range(rows)],
        },
        index=idx,
    )


def test_rebalance_windows_schedule():
    w = rebalance_windows(n_rows=100, lookback=10, hold=20)
    assert w[0] == (10, 30)
    assert w[-1] == (90, 99)  # last window ends at final row
    assert all(e > s for s, e in w)


def test_qualifying_trailing_return_and_dropna():
    df = _prices(12)
    ret = qualifying(df, i=6, lookback=3)   # price[6]/price[3]-1
    assert abs(ret["A"] - (16 / 13 - 1)) < 1e-9   # A: 13 -> 16
    assert abs(ret["B"] - 0.0) < 1e-9
    assert ret["C"] < 0                            # C falling


def test_window_return_equal_weight_buyhold():
    idx = pd.date_range("2026-01-01", periods=3, freq="D", tz="UTC")
    df = pd.DataFrame({"A": [10, 15, 20], "B": [10, 10, 10]}, index=idx)
    # A doubles (10->20 = +100%), B flat (0%); equal-weight buy-hold end value
    # = mean(20/10, 10/10) = mean(2.0, 1.0) = 1.5 -> +50%
    r = window_return(df, 0, 2, ["A", "B"])
    assert abs(r - 0.5) < 1e-9


def test_window_return_drops_incomplete_coins():
    idx = pd.date_range("2026-01-01", periods=3, freq="D", tz="UTC")
    df = pd.DataFrame({"A": [10, 15, 20], "C": [None, 10, 12]}, index=idx)
    r = window_return(df, 0, 2, ["A", "C"])   # C has NaN at start -> dropped
    assert abs(r - 1.0) < 1e-9                 # only A: +100%


def test_book_momentum_beats_market_when_winner_persists():
    df = _prices(12)
    windows = rebalance_windows(12, lookback=3, hold=3)

    def top1(ret):
        return list(ret.nlargest(1).index)

    def market(ret):
        return list(ret.index)

    mom = book_total_return(df, windows, 3, top1)   # always picks A (the winner)
    mkt = book_total_return(df, windows, 3, market)
    assert mom is not None and mkt is not None
    assert mom > mkt   # concentrating in the persistent winner beats holding all


def test_null_p_value_math():
    rep = MomentumReport(
        universe_size=50, lookback=90, hold=30, top_k=10, n_windows=40,
        start=None, end=None, momentum_return_pct=100.0,
        market_return_pct=50.0, btc=(80.0, None, None),
        null_returns=[120.0, 90.0, 80.0, 60.0],  # 1 of 4 >= 100
    )
    assert rep.null_p_value == round((1 + 1) / (4 + 1), 4)  # 0.4
    assert rep.null_mean_pct == 87.5


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
