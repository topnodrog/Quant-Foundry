"""Tests for the Phase 3 backtest data bridge (pure mapping logic).

Covers ``build_fear_greed_data`` — the ``SignalPoint`` -> ``FearGreedData``
conversion — without standing up a BacktestEngine. Runs under pytest, or
standalone: ``python tests/test_backtest_data.py``.

Note: importing ``quiverquant.backtest.data`` pulls in nautilus_trader, so this
is heavier than the ontology mapping tests but still needs no running services.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from quiverquant.backtest.data import build_fear_greed_data, build_tvl_data  # noqa: E402
from quiverquant.backtest.signals import SignalPoint, TvlTotalPoint  # noqa: E402

TS = datetime(2026, 7, 3, 0, 0, 0, tzinfo=timezone.utc)
TS_NS = int(TS.timestamp() * 1_000_000_000)


def _point(ts=TS, **payload) -> SignalPoint:
    return SignalPoint(ts=ts, entity="market", payload=payload)


def test_maps_value_and_classification():
    out = build_fear_greed_data([_point(value=20, classification="Extreme Fear")])
    assert len(out) == 1
    d = out[0]
    assert d.value == 20.0
    assert d.classification == "Extreme Fear"
    assert d.ts_event == TS_NS
    assert d.ts_init == TS_NS


def test_value_coerced_to_float():
    out = build_fear_greed_data([_point(value="55", classification="Greed")])
    assert out[0].value == 55.0
    assert isinstance(out[0].value, float)


def test_skips_missing_value():
    out = build_fear_greed_data([_point(classification="Neutral")])  # no 'value'
    assert out == []


def test_skips_non_numeric_value():
    out = build_fear_greed_data([_point(value="n/a", classification="?")])
    assert out == []


def test_missing_classification_becomes_empty_string():
    out = build_fear_greed_data([_point(value=42)])
    assert out[0].classification == ""


def test_preserves_order_and_count():
    pts = [
        _point(ts=datetime(2026, 7, 1, tzinfo=timezone.utc), value=10, classification="Extreme Fear"),
        _point(ts=datetime(2026, 7, 2, tzinfo=timezone.utc), value=90, classification="Extreme Greed"),
    ]
    out = build_fear_greed_data(pts)
    assert [d.value for d in out] == [10.0, 90.0]


def test_build_tvl_data_maps_fields():
    pts = [TvlTotalPoint(ts=TS, total_usd=1.5e10, protocol_count=25)]
    out = build_tvl_data(pts)
    assert len(out) == 1
    d = out[0]
    assert d.total_usd == 1.5e10
    assert d.protocol_count == 25
    assert d.ts_event == TS_NS and d.ts_init == TS_NS


def test_build_tvl_data_preserves_order():
    pts = [
        TvlTotalPoint(ts=datetime(2026, 7, 1, tzinfo=timezone.utc), total_usd=10.0, protocol_count=3),
        TvlTotalPoint(ts=datetime(2026, 7, 2, tzinfo=timezone.utc), total_usd=20.0, protocol_count=3),
    ]
    out = build_tvl_data(pts)
    assert [d.total_usd for d in out] == [10.0, 20.0]


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
