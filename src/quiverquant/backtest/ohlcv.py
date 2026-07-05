"""Historical OHLCV price bars via CCXT, cached in DuckDB.

The Phase 1 CCXT collector only stores *live ticker snapshots* — useless for a
backtest, which needs a continuous history. This module pulls historical OHLCV
bars with ``exchange.fetch_ohlcv`` (free, keyless on the major venues),
paginating past each venue's per-call limit, and caches them in a dedicated
``ohlcv`` DuckDB table so re-runs don't re-hit the exchange.

Timestamps are stored as tz-naive UTC wall-clock, matching ``storage.py``'s
convention for ``raw_signals`` so the two streams line up on one clock.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import TYPE_CHECKING

import ccxt

from quiverquant.config import DATA_DIR, DB_PATH

if TYPE_CHECKING:
    import pandas as pd
    import duckdb

# timeframe -> milliseconds, for pagination math
_TIMEFRAME_MS = {
    "1m": 60_000,
    "5m": 300_000,
    "15m": 900_000,
    "1h": 3_600_000,
    "4h": 14_400_000,
    "1d": 86_400_000,
}

_SCHEMA = """
CREATE TABLE IF NOT EXISTS ohlcv (
    exchange   VARCHAR   NOT NULL,
    symbol     VARCHAR   NOT NULL,
    timeframe  VARCHAR   NOT NULL,
    ts         TIMESTAMP NOT NULL,   -- bar OPEN time, tz-naive UTC
    open       DOUBLE    NOT NULL,
    high       DOUBLE    NOT NULL,
    low        DOUBLE    NOT NULL,
    close      DOUBLE    NOT NULL,
    volume     DOUBLE    NOT NULL,
    PRIMARY KEY (exchange, symbol, timeframe, ts)
);
"""


def _connect() -> "duckdb.DuckDBPyConnection":
    import duckdb

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(DB_PATH))
    con.execute(_SCHEMA)
    return con


def _timeframe_ms(timeframe: str) -> int:
    try:
        return _TIMEFRAME_MS[timeframe]
    except KeyError:  # pragma: no cover - guardrail
        raise ValueError(
            f"Unsupported timeframe {timeframe!r}; add it to _TIMEFRAME_MS"
        ) from None


def fetch_ohlcv_history(
    exchange_id: str,
    symbol: str,
    timeframe: str = "1h",
    since_ms: int | None = None,
    until_ms: int | None = None,
    per_call_limit: int = 1000,
) -> list[list[float]]:
    """Fetch raw ``[ts_ms, o, h, l, c, v]`` rows from ``since_ms`` to ``until_ms``.

    Paginates past the venue's per-call cap by advancing ``since`` to just after
    the last returned bar. ``enableRateLimit`` makes CCXT self-throttle.
    """
    exchange = getattr(ccxt, exchange_id)({"enableRateLimit": True})
    if not exchange.has.get("fetchOHLCV"):
        raise RuntimeError(f"{exchange_id} does not support fetchOHLCV")

    tf_ms = _timeframe_ms(timeframe)
    if since_ms is None:
        since_ms = exchange.milliseconds() - 30 * 86_400_000  # default: last 30d
    if until_ms is None:
        until_ms = exchange.milliseconds()

    out: list[list[float]] = []
    cursor = since_ms
    while cursor < until_ms:
        batch = exchange.fetch_ohlcv(symbol, timeframe, since=cursor, limit=per_call_limit)
        if not batch:
            break
        # some venues echo the `since` bar back; drop anything <= cursor-tf to be safe
        batch = [row for row in batch if row[0] < until_ms]
        if not batch:
            break
        out.extend(batch)
        last_ts = batch[-1][0]
        next_cursor = last_ts + tf_ms
        if next_cursor <= cursor:  # no forward progress -> stop, avoid infinite loop
            break
        cursor = next_cursor
        if len(batch) < per_call_limit:
            break  # venue had nothing more to give
    return out


def cache_ohlcv(
    exchange_id: str,
    symbol: str,
    timeframe: str,
    rows: list[list[float]],
) -> int:
    """Upsert raw CCXT rows into the ``ohlcv`` table. Returns rows written."""
    if not rows:
        return 0
    records = [
        (
            exchange_id,
            symbol,
            timeframe,
            datetime.fromtimestamp(r[0] / 1000, tz=timezone.utc).replace(tzinfo=None),
            float(r[1]),
            float(r[2]),
            float(r[3]),
            float(r[4]),
            float(r[5]),
        )
        for r in rows
    ]
    con = _connect()
    try:
        # INSERT OR REPLACE keeps the table idempotent across overlapping backfills
        con.executemany(
            "INSERT OR REPLACE INTO ohlcv "
            "(exchange, symbol, timeframe, ts, open, high, low, close, volume) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            records,
        )
    finally:
        con.close()
    return len(records)


def backfill(
    exchange_id: str,
    symbol: str,
    timeframe: str = "1h",
    days: int = 365,
) -> int:
    """Fetch the last ``days`` of bars and cache them. Returns rows cached."""
    now_ms = ccxt.Exchange.milliseconds()
    since_ms = now_ms - days * 86_400_000
    rows = fetch_ohlcv_history(exchange_id, symbol, timeframe, since_ms, now_ms)
    return cache_ohlcv(exchange_id, symbol, timeframe, rows)


def read_ohlcv_df(
    exchange_id: str,
    symbol: str,
    timeframe: str = "1h",
    start: datetime | None = None,
    end: datetime | None = None,
) -> "pd.DataFrame":
    """Read cached bars into a pandas DataFrame indexed by tz-aware UTC time,
    with columns ``open/high/low/close/volume`` — the shape
    nautilus_trader's ``BarDataWrangler`` expects.
    """
    import pandas as pd

    con = _connect()
    try:
        q = (
            "SELECT ts, open, high, low, close, volume FROM ohlcv "
            "WHERE exchange = ? AND symbol = ? AND timeframe = ?"
        )
        params: list[object] = [exchange_id, symbol, timeframe]
        if start is not None:
            q += " AND ts >= ?"
            params.append(start.replace(tzinfo=None))
        if end is not None:
            q += " AND ts < ?"
            params.append(end.replace(tzinfo=None))
        q += " ORDER BY ts"
        df = con.execute(q, params).df()
    finally:
        con.close()

    if df.empty:
        return df
    df["ts"] = pd.to_datetime(df["ts"], utc=True)
    df = df.set_index("ts")
    df.index.name = "timestamp"
    return df
