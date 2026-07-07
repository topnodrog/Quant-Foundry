"""Tests for the point-in-time momentum math (pure, synthetic — no network/DB).

Runs under pytest, or standalone: ``python tests/test_pit_momentum.py``.
"""

from __future__ import annotations

import datetime as dt
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pandas as pd  # noqa: E402

from quiverquant.features.pit_momentum import (  # noqa: E402
    PitMomentumReport,
    _active_set,
    _turnover_cost,
    pit_book_return,
)
from quiverquant.features.momentum import rebalance_windows  # noqa: E402


def test_active_set_uses_most_recent_snapshot_on_or_before():
    membership = [
        (dt.date(2021, 1, 1), {"a", "b"}),
        (dt.date(2021, 2, 1), {"b", "c"}),
        (dt.date(2021, 3, 1), {"c", "d"}),
    ]
    assert _active_set(membership, pd.Timestamp("2021-02-15", tz="UTC")) == {"b", "c"}
    assert _active_set(membership, pd.Timestamp("2021-01-01", tz="UTC")) == {"a", "b"}
    assert _active_set(membership, pd.Timestamp("2020-12-31", tz="UTC")) == set()  # before first
    assert _active_set(membership, pd.Timestamp("2099-01-01", tz="UTC")) == {"c", "d"}  # after last


def test_turnover_cost_full_entry_then_partial_churn():
    fee = 0.001  # 10 bps one-way
    # first rebalance: prev empty -> bought 100%, sold 0% -> cost = fee * 1.0
    assert abs(_turnover_cost(set(), {"a", "b"}, fee) - fee) < 1e-12
    # replace 1 of 2 names: bought 1/2, sold 1/2 -> cost = fee * (0.5 + 0.5) = fee
    assert abs(_turnover_cost({"a", "b"}, {"a", "c"}, fee) - fee) < 1e-12
    # no change: cost 0
    assert _turnover_cost({"a", "b"}, {"a", "b"}, fee) == 0.0
    # empty target: cost 0
    assert _turnover_cost({"a"}, set(), fee) == 0.0


def test_pit_book_restricts_to_membership_and_charges_fees():
    idx = pd.date_range("2021-01-01", periods=9, freq="D", tz="UTC")
    # A rises, B flat, C rises faster — but C is NOT a member, so momentum can't pick it
    price = pd.DataFrame(
        {"A": [10, 11, 12, 13, 14, 15, 16, 17, 18],
         "B": [5, 5, 5, 5, 5, 5, 5, 5, 5],
         "C": [1, 3, 6, 10, 15, 21, 28, 36, 45]},
        index=idx,
    )
    membership = [(dt.date(2021, 1, 1), {"A", "B"})]  # C excluded despite best momentum
    windows = rebalance_windows(len(price), lookback=2, hold=2)

    picked = []

    def select_top1(ret, active):
        picked.append(set(ret.index))
        return list(ret.nlargest(1).index)

    total, n = pit_book_return(price, windows, 2, membership, select_top1, fee_rate=0.0)
    # every candidate set must be a subset of the active membership (no C)
    assert all(s <= {"A", "B"} for s in picked)
    assert total is not None and n > 0


def test_pit_book_fee_reduces_return():
    idx = pd.date_range("2021-01-01", periods=9, freq="D", tz="UTC")
    price = pd.DataFrame({"A": [10, 11, 12, 13, 14, 15, 16, 17, 18],
                          "B": [5, 5, 5, 5, 5, 5, 5, 5, 5]}, index=idx)
    membership = [(dt.date(2021, 1, 1), {"A", "B"})]
    windows = rebalance_windows(len(price), lookback=2, hold=2)

    def sel(ret, active):
        return list(ret.nlargest(1).index)

    free, _ = pit_book_return(price, windows, 2, membership, sel, fee_rate=0.0)
    charged, _ = pit_book_return(price, windows, 2, membership, sel, fee_rate=0.01)
    assert charged < free  # fees drag the book down


def test_report_p_value_and_gate():
    rep = PitMomentumReport(
        lookback=90, hold=30, top_k=10, fee_bps=10.0, n_windows=40,
        start=None, end=None, momentum_return_pct=100.0,
        null_returns=[120.0, 90.0, 80.0, 60.0], priced_universe=200, median_active=55,
    )
    assert rep.null_p_value == round((1 + 1) / (4 + 1), 4)  # 0.4, fails gate
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
