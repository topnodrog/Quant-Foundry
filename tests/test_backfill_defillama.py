"""Tests for the DefiLlama TVL backfill pure mapping (history_to_records).

No network or DuckDB — just the point-filtering/dedup logic. Runs under pytest,
or standalone: ``python tests/test_backfill_defillama.py``.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from quiverquant.backfill.defillama_tvl import history_to_records  # noqa: E402

META = {"name": "Aave", "category": "Lending", "chain": "Ethereum"}
# 2021-01-01 and 2021-01-02 (UTC midnights)
D1 = 1609459200
D2 = 1609545600


def test_maps_points_to_records():
    hist = [{"date": D1, "totalLiquidityUSD": 100.0},
            {"date": D2, "totalLiquidityUSD": 200.0}]
    recs = history_to_records("aave", META, hist, set())
    assert len(recs) == 2
    r = recs[0]
    assert r["source"] == "defillama" and r["signal_type"] == "tvl_history"
    assert r["entity"] == "aave" and r["tier"] == "free"
    assert r["payload"]["tvl"] == 100.0
    assert r["payload"]["category"] == "Lending"
    assert r["payload"]["date"] == "2021-01-01"
    assert r["ts"] == datetime(2021, 1, 1, tzinfo=timezone.utc)


def test_skips_seen_days():
    hist = [{"date": D1, "totalLiquidityUSD": 100.0},
            {"date": D2, "totalLiquidityUSD": 200.0}]
    recs = history_to_records("aave", META, hist, seen_days={"2021-01-01"})
    assert [r["payload"]["date"] for r in recs] == ["2021-01-02"]


def test_dedupes_duplicate_dates_within_response():
    hist = [{"date": D1, "totalLiquidityUSD": 100.0},
            {"date": D1, "totalLiquidityUSD": 111.0}]  # same day repeated
    recs = history_to_records("aave", META, hist, set())
    assert len(recs) == 1
    assert recs[0]["payload"]["tvl"] == 100.0  # first wins


def test_since_filter():
    hist = [{"date": D1, "totalLiquidityUSD": 100.0},
            {"date": D2, "totalLiquidityUSD": 200.0}]
    since = datetime(2021, 1, 2, tzinfo=timezone.utc)
    recs = history_to_records("aave", META, hist, set(), since=since)
    assert [r["payload"]["date"] for r in recs] == ["2021-01-02"]


def test_skips_missing_fields():
    hist = [{"date": D1},                          # no tvl
            {"totalLiquidityUSD": 5.0},            # no date
            {"date": D2, "totalLiquidityUSD": 9.0}]
    recs = history_to_records("aave", META, hist, set())
    assert len(recs) == 1
    assert recs[0]["ts"] == datetime(2021, 1, 2, tzinfo=timezone.utc)


def test_tvl_coerced_to_float():
    recs = history_to_records("aave", META, [{"date": D1, "totalLiquidityUSD": 7}], set())
    assert isinstance(recs[0]["payload"]["tvl"], float)


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
