"""Point-in-time crypto universe membership from CoinMarketCap's historical
snapshots — the survivorship-bias fix for cross-sectional candidates (PLAN.md
§9 next-steps, `research/survivorship-free-universe.md`).

Candidate #6's universe was *today's* liquid top-80 (CoinGecko `/coins/markets`),
which by construction excludes every coin that died before today. CMC's public
``coinmarketcap.com/historical/YYYYMMDD/`` pages are the free fix: they're
server-rendered HTML (no login, no JS execution needed — verified against real
pages spanning 2015-2026), and they include coins that later went to zero. The
top 20 rows carry full data (rank/symbol/name/market cap); ranks 21-200 render
as a "sign up to see more" teaser that still discloses rank position, slug, and
name — enough for membership even without the market-cap number. A 2022-01-01
snapshot recovers TerraUSD and FTX Token at their pre-collapse ranks; a
2015-01-01 snapshot recovers PayCoin (rank #3 then, worthless now) — real
survivorship-bias recoveries, not hypothetical.

One request per snapshot date, no key, no rate limit observed. Store a sparse
grid (default monthly) rather than daily — the walk-forward re-run needs
membership at rebalance dates, not a continuous feed.
"""

from __future__ import annotations

import re
import time
from datetime import date, datetime, timedelta, timezone
from typing import Any

import requests

from quiverquant.config import DATA_DIR, DB_PATH

BASE = "https://coinmarketcap.com/historical"
_UA = {"User-Agent": "quant-foundry-research/0.1"}

_FULL_ROW = re.compile(r'<tr class="cmc-table-row"[^>]*>(.*?)</tr>', re.DOTALL)
_RANK = re.compile(r'sort-by__rank"><div[^>]*>(\d+)</div>')
_NAME_LINK = re.compile(
    r'href="/currencies/([^/"]+)/"[^>]*title="([^"]*)"[^>]*'
    r'class="cmc-table__column-name--symbol[^"]*">([^<]*)</a>'
)
_MARKET_CAP = re.compile(r'sort-by__market-cap"><div>\$([0-9,]+\.\d+)</div>')

# Ranks 21+ render as a locked "sign up to see more" row: no market cap, but the
# slug+name (hence rank, via position) are still in the raw HTML.
_TEASER_ROW = re.compile(
    r'<tr class="sc-c594c4ec-1 hfEsTf cmc-table-row"><td></td>'
    r'<td class="name-cell"><span class="image-placeholder"></span>'
    r'<a href="/currencies/([^/"]+)/" class="cmc-link">([^<]*)</a></td>'
    r'<td colSpan="999"[^>]*></td></tr>'
)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS universe_snapshot (
    snapshot_date DATE    NOT NULL,
    rank          INTEGER NOT NULL,
    slug          VARCHAR NOT NULL,
    name          VARCHAR NOT NULL,
    symbol        VARCHAR,           -- known for rank<=20 only (teaser rows omit it)
    market_cap    DOUBLE,            -- known for rank<=20 only
    PRIMARY KEY (snapshot_date, rank)
);
"""


def _connect():
    import duckdb

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(DB_PATH))
    con.execute(_SCHEMA)
    return con


def fetch_snapshot_html(d: date, max_retries: int = 3) -> str | None:
    """GET the historical page for ``d``. Returns None on a non-200 (dates
    before CMC's 2013 launch, or a transient failure after retries)."""
    url = f"{BASE}/{d.strftime('%Y%m%d')}/"
    delay = 2.0
    for attempt in range(max_retries):
        try:
            resp = requests.get(url, headers=_UA, timeout=30)
        except requests.RequestException:
            if attempt == max_retries - 1:
                return None
            time.sleep(delay)
            delay *= 2
            continue
        if resp.status_code == 200:
            return resp.text
        if resp.status_code == 404:
            return None
        if attempt < max_retries - 1:
            time.sleep(delay)
            delay *= 2
    return None


def parse_snapshot(html: str) -> list[dict[str, Any]]:
    """Pure parse: top-200 ``{rank, slug, name, symbol, market_cap}`` rows.

    Ranks 1-20 come from ``_FULL_ROW`` (symbol + market cap present); ranks
    21+ come from the locked ``_TEASER_ROW`` (symbol/market_cap left None —
    resolved later, if needed, by name against a separate ticker source).
    Rank for teaser rows is positional (they render in rank order with no
    rank number in the markup), continuing from the last full row.
    """
    rows: list[dict[str, Any]] = []
    for block in _FULL_ROW.findall(html):
        rank_m = _RANK.search(block)
        link_m = _NAME_LINK.search(block)
        if not rank_m or not link_m:
            continue
        mcap_m = _MARKET_CAP.search(block)
        slug, name, symbol = link_m.groups()
        rows.append({
            "rank": int(rank_m.group(1)),
            "slug": slug,
            "name": name,
            "symbol": symbol,
            "market_cap": float(mcap_m.group(1).replace(",", "")) if mcap_m else None,
        })

    next_rank = (rows[-1]["rank"] + 1) if rows else 21
    for slug, name in _TEASER_ROW.findall(html):
        rows.append({
            "rank": next_rank, "slug": slug, "name": name,
            "symbol": None, "market_cap": None,
        })
        next_rank += 1
    return rows


def stored_dates() -> set[date]:
    con = _connect()
    try:
        rows = con.execute("SELECT DISTINCT snapshot_date FROM universe_snapshot").fetchall()
    finally:
        con.close()
    return {r[0] for r in rows}


def store_snapshot(d: date, rows: list[dict[str, Any]]) -> int:
    if not rows:
        return 0
    con = _connect()
    try:
        con.executemany(
            "INSERT OR REPLACE INTO universe_snapshot "
            "(snapshot_date, rank, slug, name, symbol, market_cap) VALUES (?, ?, ?, ?, ?, ?)",
            [(d, r["rank"], r["slug"], r["name"], r["symbol"], r["market_cap"]) for r in rows],
        )
    finally:
        con.close()
    return len(rows)


def _date_range(start: date, end: date, step_days: int) -> list[date]:
    out = []
    d = start
    while d <= end:
        out.append(d)
        d += timedelta(days=step_days)
    return out


def backfill_snapshots(
    start: str = "2018-01-01",
    end: str | None = None,
    step_days: int = 30,
    pause: float = 1.5,
) -> dict[str, Any]:
    """Fetch + store one snapshot every ``step_days`` from ``start`` to ``end``
    (default today). Idempotent — already-stored dates are skipped so a retry
    after a partial run only fetches what's missing."""
    start_d = datetime.strptime(start, "%Y-%m-%d").date()
    end_d = datetime.strptime(end, "%Y-%m-%d").date() if end else datetime.now(timezone.utc).date()
    have = stored_dates()

    fetched, failed, skipped = 0, [], 0
    for d in _date_range(start_d, end_d, step_days):
        if d in have:
            skipped += 1
            continue
        html = fetch_snapshot_html(d)
        if html is None:
            failed.append(d.isoformat())
            print(f"[cmc-snapshots] {d} FAILED (no page)")
            continue
        rows = parse_snapshot(html)
        n = store_snapshot(d, rows)
        fetched += 1
        print(f"[cmc-snapshots] {d}: {n} ranked coins")
        time.sleep(pause)
    return {
        "snapshots_fetched": fetched, "snapshots_skipped": skipped,
        "snapshots_failed": failed, "start": start_d.isoformat(), "end": end_d.isoformat(),
    }


def universe_at(d: date, top_n: int = 80) -> list[dict[str, Any]]:
    """Rows for exactly the stored snapshot date ``d`` (no nearest-date
    fallback — the caller controls the grid via ``backfill_snapshots``)."""
    con = _connect()
    try:
        rows = con.execute(
            "SELECT rank, slug, name, symbol, market_cap FROM universe_snapshot "
            "WHERE snapshot_date = ? AND rank <= ? ORDER BY rank",
            [d, top_n],
        ).fetchall()
    finally:
        con.close()
    return [
        {"rank": r, "slug": s, "name": n, "symbol": sym, "market_cap": mc}
        for r, s, n, sym, mc in rows
    ]


def all_snapshot_dates() -> list[date]:
    con = _connect()
    try:
        rows = con.execute(
            "SELECT DISTINCT snapshot_date FROM universe_snapshot ORDER BY snapshot_date"
        ).fetchall()
    finally:
        con.close()
    return [r[0] for r in rows]


def distinct_members(top_n: int = 80) -> list[dict[str, Any]]:
    """Every ``(slug, name)`` that was EVER ranked <= ``top_n`` across all
    stored snapshots, with its best (lowest) rank ever seen and, if any
    snapshot caught it in the top 20, its known symbol. This is the real
    survivorship-free candidate universe — bigger than any single date's top
    N because it accumulates every coin that passed through that tier,
    including ones that later fell out or died.
    """
    con = _connect()
    try:
        rows = con.execute(
            "SELECT slug, any_value(name), min(rank) AS best_rank, "
            "max(symbol) FILTER (symbol IS NOT NULL) AS symbol, "
            "min(snapshot_date) AS first_seen, max(snapshot_date) AS last_seen "
            "FROM universe_snapshot WHERE rank <= ? "
            "GROUP BY slug ORDER BY best_rank",
            [top_n],
        ).fetchall()
    finally:
        con.close()
    return [
        {
            "slug": slug, "name": name, "best_rank": best_rank, "symbol": symbol,
            "first_seen": first_seen, "last_seen": last_seen,
        }
        for slug, name, best_rank, symbol, first_seen, last_seen in rows
    ]


def print_backfill_summary(s: dict[str, Any]) -> None:
    print(f"\n=== CMC historical snapshots: {s['start']} -> {s['end']} ===")
    print(f"  fetched {s['snapshots_fetched']}, skipped {s['snapshots_skipped']} (already stored), "
          f"failed {len(s['snapshots_failed'])}")
    if s["snapshots_failed"]:
        print(f"  failed dates: {', '.join(s['snapshots_failed'])}")
    dates = all_snapshot_dates()
    if dates:
        print(f"  total snapshots stored: {len(dates)} ({dates[0]} .. {dates[-1]})")
        members = distinct_members(top_n=80)
        print(f"  distinct coins ever in top-80 across all snapshots: {len(members)}")
