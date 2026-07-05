"""Read Phase 1 ``raw_signals`` back out as ordered time series.

The backtest needs alt-data signals as a clean, time-ordered stream so they can
be interleaved with price bars without lookahead bias. This module is the pure
DuckDB read side; turning a series into nautilus custom ``Data`` objects lives in
``data.py`` so this stays dependency-light and unit-testable.

Only Fear & Greed currently has real backtestable history (see PLAN.md §9 /
README) — but the reader is signal-type-agnostic so new series become usable the
moment they accumulate history.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from quiverquant.storage import get_connection


@dataclass(frozen=True)
class SignalPoint:
    """One observation in a signal series. ``ts`` is tz-aware UTC."""

    ts: datetime
    entity: str | None
    payload: dict[str, Any]


def read_signal_points(
    signal_type: str,
    start: datetime | None = None,
    end: datetime | None = None,
) -> list[SignalPoint]:
    """Return all ``raw_signals`` rows of ``signal_type``, ordered by event time.

    Stored timestamps are tz-naive UTC wall-clock (see ``storage.py``); this
    re-attaches UTC so callers get tz-aware datetimes.
    """
    q = "SELECT ts, entity, payload FROM raw_signals WHERE signal_type = ?"
    params: list[object] = [signal_type]
    if start is not None:
        q += " AND ts >= ?"
        params.append(start.replace(tzinfo=None))
    if end is not None:
        q += " AND ts < ?"
        params.append(end.replace(tzinfo=None))
    q += " ORDER BY ts"

    con = get_connection()
    try:
        rows = con.execute(q, params).fetchall()
    finally:
        con.close()

    points: list[SignalPoint] = []
    for ts, entity, payload in rows:
        if isinstance(ts, datetime) and ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        parsed = payload if isinstance(payload, dict) else json.loads(payload)
        points.append(SignalPoint(ts=ts, entity=entity, payload=parsed))
    return points
