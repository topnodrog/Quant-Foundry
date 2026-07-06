"""Tests for the cross-sectional book math (pure, synthetic frames — no network).

Runs under pytest, or standalone: ``python tests/test_cross_section.py``.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pandas as pd  # noqa: E402

from quiverquant.features.cross_section import (  # noqa: E402
    CrossSectionReport,
    book_daily_returns,
    total_return_pct,
)


def _prices() -> pd.DataFrame:
    # A doubles (100->200), B is flat (50->50), C lists late (NaN then 10->20).
    idx = pd.to_datetime(["2026-01-01", "2026-01-02", "2026-01-03"], utc=True)
    return pd.DataFrame(
        {"A": [100.0, 150.0, 200.0], "B": [50.0, 50.0, 50.0], "C": [None, 10.0, 20.0]},
        index=idx,
    )


def test_total_return_single_asset():
    df = _prices()
    r = total_return_pct(book_daily_returns(df, ["A"]))
    assert r == 100.0  # 100 -> 200


def test_flat_asset_zero_return():
    df = _prices()
    assert total_return_pct(book_daily_returns(df, ["B"])) == 0.0


def test_equal_weight_averages_available_constituents():
    df = _prices()
    # day2: A +50%, B 0%, C NaN (no prior) -> mean(0.5, 0.0) = 0.25
    # day3: A +33.3%, B 0%, C +100% -> mean(0.3333, 0, 1.0) = 0.4444
    daily = book_daily_returns(df, ["A", "B", "C"])
    assert abs(daily.iloc[1] - 0.25) < 1e-9
    assert abs(daily.iloc[2] - (1 / 3 + 0 + 1.0) / 3) < 1e-9


def test_unknown_ids_ignored():
    df = _prices()
    assert book_daily_returns(df, ["NOPE"]) is None


def _report(conv: float, null: list[float]) -> CrossSectionReport:
    return CrossSectionReport(
        n_universe=10, conviction=[("X", "x")], start=None, end=None,
        conviction_return_pct=conv, universe_return_pct=None, btc_return_pct=None,
        null_returns=null, n_permutations=len(null),
    )


def test_null_p_value():
    # 2 of 4 random subsets matched/beat the conviction book (50, 80 >= 60)
    rep = _report(60.0, [50.0, 80.0, 30.0, 20.0])
    # (1 + 1) / (4 + 1) = 0.4  (only 80 >= 60 -> 1 ge)
    assert rep.null_p_value == 0.4


def test_null_mean():
    rep = _report(60.0, [10.0, 20.0, 30.0])
    assert rep.null_mean_pct == 20.0


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
