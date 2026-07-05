"""Tests for the GitHub dev-activity backfill pure mapping (weekly_to_records).

No network or DuckDB. Runs under pytest, or standalone:
``python tests/test_backfill_github.py``.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from quiverquant.backfill.github_dev import weekly_to_records  # noqa: E402

# 2021-01-03 and 2021-01-10 (GitHub week starts are Sundays, UTC midnight)
W1 = 1609632000
W2 = 1610236800


def _weekly():
    return {
        W1: {"commits": 5, "additions": 100, "deletions": 20},
        W2: {"commits": 0, "additions": 0, "deletions": 0},
    }


def test_maps_weeks_to_records():
    recs = weekly_to_records("ethereum/go-ethereum", _weekly(), set())
    assert len(recs) == 2
    r = recs[0]
    assert r["source"] == "github" and r["signal_type"] == "dev_activity_history"
    assert r["entity"] == "ethereum/go-ethereum"
    assert r["payload"]["commits"] == 5
    assert r["payload"]["additions"] == 100
    assert r["ts"] == datetime(2021, 1, 3, tzinfo=timezone.utc)


def test_keeps_zero_commit_weeks():
    recs = weekly_to_records("r", _weekly(), set())
    assert [r["payload"]["commits"] for r in recs] == [5, 0]


def test_orders_by_week_ascending():
    unordered = {W2: {"commits": 1, "additions": 0, "deletions": 0},
                 W1: {"commits": 2, "additions": 0, "deletions": 0}}
    recs = weekly_to_records("r", unordered, set())
    assert [r["payload"]["week"] for r in recs] == ["2021-01-03", "2021-01-10"]


def test_skips_seen_weeks():
    recs = weekly_to_records("r", _weekly(), seen_weeks={"2021-01-03"})
    assert [r["payload"]["week"] for r in recs] == ["2021-01-10"]


def test_since_filter():
    since = datetime(2021, 1, 10, tzinfo=timezone.utc)
    recs = weekly_to_records("r", _weekly(), set(), since=since)
    assert [r["payload"]["week"] for r in recs] == ["2021-01-10"]


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
