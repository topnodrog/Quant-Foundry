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
class TvlTotalPoint:
    """Aggregate DeFi TVL for one day. ``ts`` is tz-aware UTC (day start)."""

    ts: datetime
    total_usd: float
    protocol_count: int


@dataclass(frozen=True)
class DevTotalPoint:
    """Market-wide developer activity for one ISO week (commits summed across the
    tracked core repos). ``ts`` is tz-aware UTC (week start)."""

    ts: datetime
    total_commits: int
    repo_count: int


@dataclass(frozen=True)
class SentimentPoint:
    """Monthly crypto-news net sentiment (avg positive-minus-negative). ``ts`` is
    tz-aware UTC, stamped at the first day of the month AFTER the sampled one
    (so backtests learn it only once that month has closed — no lookahead)."""

    ts: datetime
    net_sentiment: float


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


def read_daily_tvl_total(
    start: datetime | None = None,
    end: datetime | None = None,
) -> list[TvlTotalPoint]:
    """Sum ``tvl_history`` across all protocols per day into one market-wide
    DeFi TVL series — a risk-on/off proxy that aligns with a BTC backtest better
    than any single protocol. Ordered by day.
    """
    q = (
        "SELECT CAST(ts AS DATE) AS d, "
        "SUM(CAST(payload->>'$.tvl' AS DOUBLE)) AS total, "
        "COUNT(*) AS n "
        "FROM raw_signals WHERE signal_type = 'tvl_history'"
    )
    params: list[object] = []
    if start is not None:
        q += " AND ts >= ?"
        params.append(start.replace(tzinfo=None))
    if end is not None:
        q += " AND ts < ?"
        params.append(end.replace(tzinfo=None))
    q += " GROUP BY 1 ORDER BY 1"

    con = get_connection()
    try:
        rows = con.execute(q, params).fetchall()
    finally:
        con.close()

    out: list[TvlTotalPoint] = []
    for day, total, n in rows:
        ts = datetime(day.year, day.month, day.day, tzinfo=timezone.utc)
        out.append(TvlTotalPoint(ts=ts, total_usd=float(total or 0.0), protocol_count=int(n)))
    return out


def read_weekly_dev_total(
    start: datetime | None = None,
    end: datetime | None = None,
) -> list[DevTotalPoint]:
    """Sum ``dev_activity_history`` commits across all tracked repos per week into
    one market-wide "builder activity" series — a shipping-momentum proxy. Rows
    are weekly (one per repo per ISO week); ordered by week.
    """
    q = (
        "SELECT CAST(ts AS DATE) AS d, "
        "SUM(CAST(payload->>'$.commits' AS BIGINT)) AS total, "
        "COUNT(DISTINCT entity) AS n "
        "FROM raw_signals WHERE signal_type = 'dev_activity_history'"
    )
    params: list[object] = []
    if start is not None:
        q += " AND ts >= ?"
        params.append(start.replace(tzinfo=None))
    if end is not None:
        q += " AND ts < ?"
        params.append(end.replace(tzinfo=None))
    q += " GROUP BY 1 ORDER BY 1"

    con = get_connection()
    try:
        rows = con.execute(q, params).fetchall()
    finally:
        con.close()

    out: list[DevTotalPoint] = []
    for day, total, n in rows:
        ts = datetime(day.year, day.month, day.day, tzinfo=timezone.utc)
        out.append(DevTotalPoint(ts=ts, total_commits=int(total or 0), repo_count=int(n)))
    return out


def read_monthly_sentiment(
    start: datetime | None = None,
    end: datetime | None = None,
) -> list[SentimentPoint]:
    """Read the backfilled monthly crypto-news sentiment series, ordered by time."""
    q = (
        "SELECT ts, CAST(payload->>'$.net_sentiment' AS DOUBLE) AS s "
        "FROM raw_signals WHERE signal_type = 'news_sentiment' AND s IS NOT NULL"
    )
    params: list[object] = []
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

    out: list[SentimentPoint] = []
    for ts, s in rows:
        if isinstance(ts, datetime) and ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        out.append(SentimentPoint(ts=ts, net_sentiment=float(s)))
    return out
