"""Daily price history for the resolved VC tokens (path 1, step B).

Uses **CCXT** (already wired for BTC in ``backtest/ohlcv.py``) rather than
CoinGecko: as of 2026-07 CoinGecko's ``/coins/{id}/market_chart`` history endpoint
requires a Demo API key (401 without one), while CCXT's ``fetch_ohlcv`` is keyless
on the major venues. We try a few exchanges / quote currencies per token symbol,
take the daily close, and store one price per token per UTC day in a
``token_price_history`` DuckDB table (keyed by the token's gecko_id so the
downstream cross-sectional backtest is unchanged), deduped and idempotent.

Trade-off vs CoinGecko: only tokens listed on a major CEX get history, and only
back to their listing there — but that's the liquid, tradeable subset anyway.
"""

from __future__ import annotations

from datetime import datetime, timezone

import ccxt

from quiverquant.backtest.ohlcv import fetch_ohlcv_history
from quiverquant.config import DATA_DIR, DB_PATH
from quiverquant.features.token_resolve import read_map

# Venues to try, in order, with the quote currencies each tends to use. First
# combo that returns bars wins.
_EXCHANGE_QUOTES = [
    ("binance", ["USDT"]),
    ("okx", ["USDT"]),
    ("kucoin", ["USDT"]),
    ("gateio", ["USDT"]),
    ("coinbase", ["USD", "USDT"]),
    ("kraken", ["USD", "USDT"]),
]

# History start — far enough back to cover any of these tokens' listings.
_SINCE_MS = int(datetime(2015, 1, 1, tzinfo=timezone.utc).timestamp() * 1000)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS token_price_history (
    gecko_id  VARCHAR NOT NULL,
    ts        DATE    NOT NULL,   -- UTC day
    price     DOUBLE  NOT NULL,   -- USD, close-equivalent
    PRIMARY KEY (gecko_id, ts)
);
"""


def _connect():
    import duckdb

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(DB_PATH))
    con.execute(_SCHEMA)
    return con


def fetch_daily_closes(base_symbol: str) -> tuple[str, list[tuple[object, float]]]:
    """Find ``base_symbol`` on a major venue and return ``(source, [(day, close)])``.

    Tries each exchange/quote combo until one yields bars. ``source`` is like
    ``binance:UNI/USDT`` for provenance; empty list if the token isn't listed
    anywhere we try.
    """
    for exchange_id, quotes in _EXCHANGE_QUOTES:
        ex = _exchange(exchange_id)
        if ex is None:
            continue
        for quote in quotes:
            symbol = f"{base_symbol}/{quote}"
            if symbol not in ex.markets:
                continue
            try:
                rows = fetch_ohlcv_history(
                    exchange_id, symbol, "1d", since_ms=_SINCE_MS, per_call_limit=1000,
                    exchange=ex,
                )
            except Exception as e:  # noqa: BLE001 - venue hiccup, try the next combo
                # Surface it: a silent skip here made venue rate-bans look like
                # "token not listed anywhere" during the first universe collect.
                print(f"  [prices] {symbol} on {exchange_id}: {type(e).__name__}, trying next venue")
                continue
            if rows:
                closes = [
                    (datetime.fromtimestamp(r[0] / 1000, tz=timezone.utc).date(), float(r[4]))
                    for r in rows
                ]
                return f"{exchange_id}:{symbol}", closes
    return "", []


# One long-lived instance per exchange: keeps load_markets to a single call AND
# keeps CCXT's per-instance rate limiter warm across a whole bulk collect —
# fresh instances per symbol start unthrottled and get the IP rate-banned.
_EXCHANGE_CACHE: dict[str, "ccxt.Exchange | None"] = {}


def _exchange(exchange_id: str) -> "ccxt.Exchange | None":
    if exchange_id not in _EXCHANGE_CACHE:
        try:
            ex = getattr(ccxt, exchange_id)({"enableRateLimit": True})
            ex.load_markets()
            _EXCHANGE_CACHE[exchange_id] = ex
        except Exception:  # noqa: BLE001 - exchange unreachable, skip it
            _EXCHANGE_CACHE[exchange_id] = None
    return _EXCHANGE_CACHE[exchange_id]


def cache_prices(gecko_id: str, closes: list[tuple[object, float]]) -> int:
    """Upsert daily closes (one per UTC day — last wins)."""
    by_day: dict[object, float] = {day: price for day, price in closes}
    if not by_day:
        return 0
    records = [(gecko_id, day, price) for day, price in by_day.items()]
    con = _connect()
    try:
        con.executemany(
            "INSERT OR REPLACE INTO token_price_history (gecko_id, ts, price) "
            "VALUES (?, ?, ?)",
            records,
        )
    finally:
        con.close()
    return len(records)


def collect_all(pause: float = 0.0, days: str = "max") -> dict[str, int]:
    """Fetch + cache daily closes for every token in ``vc_token_map`` via CCXT.

    Returns ``{gecko_id: rows_cached}``. CCXT self-throttles (``enableRateLimit``),
    so no manual pause is needed; ``pause``/``days`` are kept for CLI compatibility.
    Soft-fails a token that isn't listed anywhere so one miss doesn't abort the run.
    """
    resolutions = read_map()
    out: dict[str, int] = {}
    for r in resolutions:
        try:
            source, closes = fetch_daily_closes(r.symbol)
            n = cache_prices(r.gecko_id, closes)
            out[r.gecko_id] = n
            tag = source or "not listed on tried venues"
            print(f"[prices] {r.company:20} {r.symbol:8} {n:5} days  {tag}")
        except Exception as e:  # noqa: BLE001 - soft-fail one token, keep going
            out[r.gecko_id] = 0
            print(f"[prices] {r.company:20} {r.symbol:8} FAILED ({e})")
    return out


def read_price_df(gecko_ids: list[str] | None = None, start=None, end=None):
    """Wide DataFrame: DATE index, one column per gecko_id of daily USD price."""
    import pandas as pd

    con = _connect()
    try:
        q = "SELECT gecko_id, ts, price FROM token_price_history"
        clauses, params = [], []
        if gecko_ids:
            placeholders = ",".join("?" for _ in gecko_ids)
            clauses.append(f"gecko_id IN ({placeholders})")
            params.extend(gecko_ids)
        if start is not None:
            clauses.append("ts >= ?")
            params.append(start)
        if end is not None:
            clauses.append("ts < ?")
            params.append(end)
        if clauses:
            q += " WHERE " + " AND ".join(clauses)
        q += " ORDER BY ts"
        df = con.execute(q, params).df()
    finally:
        con.close()

    if df.empty:
        return df
    df["ts"] = pd.to_datetime(df["ts"], utc=True)
    wide = df.pivot(index="ts", columns="gecko_id", values="price").sort_index()
    wide.index.name = "date"
    return wide


def coverage_summary() -> list[tuple[str, int, object, object]]:
    """Per-token (gecko_id, day_count, first_day, last_day) for what's cached."""
    con = _connect()
    try:
        rows = con.execute(
            "SELECT gecko_id, count(*), min(ts), max(ts) FROM token_price_history "
            "GROUP BY gecko_id ORDER BY count(*) DESC"
        ).fetchall()
    finally:
        con.close()
    return rows
