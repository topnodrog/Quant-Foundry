"""Dead/delisted-coin price history from Binance's public data archive
(PLAN.md §9 next-steps, `research/survivorship-free-universe.md`).

CCXT's ``fetch_ohlcv`` (what ``backtest/ohlcv.py`` and ``features/token_prices.py``
use today) can only see markets Binance still lists — exactly the survivorship
hole in candidate #6's universe. ``data.binance.vision`` is Binance's own public
archive of monthly kline zips, append-only, so a pair's history stays downloadable
after delisting. Verified against **BTCST/USDT** (delisted 2021 for wash-trading —
June 2021 klines download fine) and **LUNA/USDT** (the pre-collapse token — April
2022 klines, weeks before it went to zero, download fine). Free, keyless, no rate
limit observed.

Same row shape as CCXT's ``fetch_ohlcv`` (``[ts_ms, o, h, l, c, v]`` — Binance's
archive CSV has 12 columns; this module keeps the first 6 and drops
quote-volume/trade-count/taker-volume/ignore), so backfilled bars go straight into
the *existing* ``ohlcv`` table via ``backtest.ohlcv.cache_ohlcv`` under
``exchange="binance"`` — no new schema, and archive coverage transparently fills
gaps beside anything the live CCXT collector already cached for the same pair.
"""

from __future__ import annotations

import io
import zipfile
from datetime import date

import requests

from quiverquant.backtest.ohlcv import cache_ohlcv, read_ohlcv_df

_URL = "https://data.binance.vision/data/spot/monthly/klines/{pair}/1d/{pair}-1d-{year}-{month:02d}.zip"


def _pair(symbol: str) -> str:
    """``BTC/USDT`` -> ``BTCUSDT`` (the archive's concatenated pair naming)."""
    return symbol.replace("/", "")


def fetch_month(symbol: str, year: int, month: int, timeout: int = 30) -> list[list[float]]:
    """Download and parse one month of daily klines for ``symbol`` (CCXT-style,
    e.g. ``BTCST/USDT``). Returns ``[]`` if the pair/month has no archive (never
    listed, or requested before the pair existed) — not every gap is an error."""
    url = _URL.format(pair=_pair(symbol), year=year, month=month)
    resp = requests.get(url, timeout=timeout)
    if resp.status_code != 200:
        return []
    return parse_kline_zip(resp.content)


def parse_kline_zip(content: bytes) -> list[list[float]]:
    """Pure parse: the archive's zipped, headerless 12-column kline CSV ->
    ``[[ts_ms, open, high, low, close, volume], ...]``."""
    zf = zipfile.ZipFile(io.BytesIO(content))
    name = zf.namelist()[0]
    with zf.open(name) as f:
        text = f.read().decode("utf-8")
    rows = []
    for line in text.splitlines():
        if not line.strip():
            continue
        fields = line.split(",")
        if fields[0].strip().lower() == "open_time":  # some months ship a header row
            continue
        ts, o, h, l, c, v = fields[:6]
        rows.append([_ts_to_ms(ts), float(o), float(h), float(l), float(c), float(v)])
    return rows


def _ts_to_ms(raw: str) -> float:
    """Normalize a kline open_time to epoch MILLISECONDS. Binance switched the
    archive's unit from ms to microseconds in ~2025 files; a real ms timestamp for
    2010-2035 is ~1e12, microseconds ~1e15, so anything above 1e14 is µs → /1000."""
    ts = float(raw)
    if ts > 1e14:
        ts /= 1000.0
    return ts


def _iter_months(start_year: int, start_month: int, end_year: int, end_month: int):
    y, m = start_year, start_month
    while (y, m) <= (end_year, end_month):
        yield y, m
        m += 1
        if m > 12:
            y, m = y + 1, 1


def archive_closes(
    symbol: str,
    start_year: int = 2017,
    start_month: int = 1,
    end_year: int | None = None,
    end_month: int | None = None,
) -> list[tuple[object, float]]:
    """Every month of daily closes for ``symbol`` from the archive, as
    ``[(day, close), ...]`` — the same shape ``token_prices.fetch_daily_closes``
    returns, so it's a drop-in fallback when a coin is no longer live on any
    CCXT-reachable venue. Pure fetch, no DB write. Months with no archive data
    (pair not listed yet, or delisted) are skipped silently."""
    from datetime import datetime, timezone

    today = date.today()
    end_year = end_year or today.year
    end_month = end_month or today.month

    closes: list[tuple[object, float]] = []
    for y, m in _iter_months(start_year, start_month, end_year, end_month):
        for row in fetch_month(symbol, y, m):
            day = datetime.fromtimestamp(row[0] / 1000, tz=timezone.utc).date()
            closes.append((day, row[4]))
    return closes


def backfill_symbol(
    symbol: str,
    start_year: int = 2017,
    start_month: int = 1,
    end_year: int | None = None,
    end_month: int | None = None,
) -> int:
    """Backfill every month of daily archive klines for ``symbol`` into the
    shared ``ohlcv`` table (``exchange="binance"``). Idempotent — re-running
    just re-fetches and ``INSERT OR REPLACE``s the same rows. Returns bars
    cached. Consecutive months with no archive data (pair not listed yet, or
    delisted) are skipped silently; that's normal, not a failure.
    """
    today = date.today()
    end_year = end_year or today.year
    end_month = end_month or today.month

    total = 0
    for y, m in _iter_months(start_year, start_month, end_year, end_month):
        rows = fetch_month(symbol, y, m)
        if not rows:
            continue
        total += cache_ohlcv("binance", symbol, "1d", rows)
    return total


def coverage(symbol: str) -> tuple[int, object, object]:
    """(day_count, first_day, last_day) currently cached for ``symbol`` on
    Binance (archive + any live-collected bars share the same table)."""
    df = read_ohlcv_df("binance", symbol, "1d")
    if df.empty:
        return 0, None, None
    return len(df), df.index[0].date(), df.index[-1].date()


def print_backfill_result(symbol: str, added: int) -> None:
    n, first, last = coverage(symbol)
    span = f"{first} .. {last}" if first else "no data"
    print(f"[binance-vision] {symbol}: +{added} bars this run, {n} total cached ({span})")
