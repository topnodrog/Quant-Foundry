"""Point-in-time universe resolution + pricing (PLAN.md §9 step 2).

Candidate #6's original universe was *today's* liquid top-80, which excludes every
coin that died before today. `backfill/cmc_snapshots.py` fixed the MEMBERSHIP half
(417 coins ever ranked top-80, 2018-2026, dead coins included). This module joins
that membership to PRICE data so a survivorship-free backtest becomes possible:

1. **Resolve** each `universe_snapshot` member (CMC slug + name) to a ticker.
   Members that ever cracked the top-20 already carry a symbol (the full HTML rows);
   the rest (ranks 21-80, ~83% of any snapshot) come as name-only teaser rows and are
   matched against CoinGecko's full ``/coins/list`` — keyless, and critically it
   INCLUDES delisted coins (unlike ``/coins/markets``, which would silently re-introduce
   survivorship bias at the resolution step). Ambiguous normalized-name collisions are
   flagged, not silently picked.
2. **Price** each resolved ticker, source priority: (a) Binance's public archive
   (`backfill/binance_vision.py`) FIRST, because it survives delisting; (b) CCXT live,
   for coins still trading but never on Binance; (c) accept the gap. Stored in
   ``pit_price_history`` keyed by CMC slug so the backtest joins price↔membership on one key.

Known identity caveats (documented, not silently swallowed): a reused ticker (LUNA →
Terra 2.0 after the 2022 collapse) means one archive series can splice two assets across
the reuse date; normalized-name matching can mis-map a homonym when the member never
carried its own symbol. Both are flagged where detectable and noted in the backtest output.
"""

from __future__ import annotations

import re

from quiverquant.config import DATA_DIR, DB_PATH

_SCHEMA = """
CREATE TABLE IF NOT EXISTS coingecko_coin (
    id     VARCHAR PRIMARY KEY,
    symbol VARCHAR,
    name   VARCHAR
);
CREATE TABLE IF NOT EXISTS universe_symbol (
    slug      VARCHAR PRIMARY KEY,   -- CMC slug from universe_snapshot
    name      VARCHAR,
    symbol    VARCHAR,               -- resolved ticker; NULL if unresolved
    source    VARCHAR,               -- 'cmc_top20' | 'coingecko_name' | 'unresolved'
    ambiguous BOOLEAN                -- >1 coingecko coin shared the normalized name
);
CREATE TABLE IF NOT EXISTS pit_price_history (
    slug   VARCHAR NOT NULL,
    ts     DATE    NOT NULL,
    price  DOUBLE  NOT NULL,
    PRIMARY KEY (slug, ts)
);
"""


def _connect():
    import duckdb

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(DB_PATH))
    con.execute(_SCHEMA)
    return con


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


# --- CoinGecko full coin list (keyless, includes delisted) --------------------

def refresh_coingecko_list() -> int:
    """Fetch CoinGecko's full ``/coins/list`` and cache it. ONE request, ~17k coins.
    Includes delisted/dead coins — the whole point vs. ``/coins/markets``."""
    from quiverquant.features.token_resolve import _cg_get

    coins = _cg_get("/coins/list", {"include_platform": "false"})
    rows = [(c["id"], str(c.get("symbol", "")).upper(), c.get("name", "")) for c in coins if c.get("id")]
    con = _connect()
    try:
        con.execute("DELETE FROM coingecko_coin")
        con.executemany("INSERT OR REPLACE INTO coingecko_coin (id, symbol, name) VALUES (?, ?, ?)", rows)
    finally:
        con.close()
    return len(rows)


def _coingecko_name_index(con) -> dict[str, list[tuple[str, str]]]:
    """normalized-name -> [(id, symbol), ...]. A list because names collide."""
    rows = con.execute("SELECT id, symbol, name FROM coingecko_coin").fetchall()
    idx: dict[str, list[tuple[str, str]]] = {}
    for cid, symbol, name in rows:
        idx.setdefault(_norm(name), []).append((cid, symbol))
    return idx


def _coingecko_id_index(con) -> dict[str, str]:
    """CoinGecko id -> symbol. CMC slugs very often equal the CoinGecko id even
    when the display names have drifted apart (CMC 'FTX Token' vs CoinGecko 'FTX',
    both id 'ftx-token'), so this recovers matches a name join misses."""
    rows = con.execute("SELECT id, symbol FROM coingecko_coin").fetchall()
    return {cid: symbol for cid, symbol in rows}


# --- symbol resolution --------------------------------------------------------

def resolve_symbols(top_n: int = 80) -> dict:
    """Resolve every distinct member ever ranked <= ``top_n`` to a ticker.

    Members with a stored symbol (top-20 rows) resolve directly. The rest match
    normalized-name against the cached CoinGecko list. Rebuilds ``universe_symbol``
    wholesale. Returns a coverage summary."""
    from quiverquant.backfill.cmc_snapshots import distinct_members

    members = distinct_members(top_n=top_n)
    con = _connect()
    try:
        if con.execute("SELECT count(*) FROM coingecko_coin").fetchone()[0] == 0:
            raise RuntimeError("coingecko_coin empty — run refresh first (resolve-universe --refresh)")
        name_idx = _coingecko_name_index(con)
        id_idx = _coingecko_id_index(con)

        con.execute("DELETE FROM universe_symbol")
        direct = by_slug = matched = ambiguous = unresolved = 0
        rows = []
        for m in members:
            slug, name, symbol = m["slug"], m["name"], m["symbol"]
            if symbol:
                rows.append((slug, name, symbol, "cmc_top20", False))
                direct += 1
                continue
            # CMC slug == CoinGecko id is a stronger key than a drifted display name.
            if slug in id_idx and id_idx[slug]:
                rows.append((slug, name, id_idx[slug], "coingecko_id", False))
                by_slug += 1
                continue
            hits = name_idx.get(_norm(name), [])
            if not hits:
                rows.append((slug, name, None, "unresolved", False))
                unresolved += 1
            else:
                # first hit's ticker; flag if the normalized name was shared
                rows.append((slug, name, hits[0][1], "coingecko_name", len(hits) > 1))
                matched += 1
                if len(hits) > 1:
                    ambiguous += 1
        con.executemany(
            "INSERT OR REPLACE INTO universe_symbol (slug, name, symbol, source, ambiguous) "
            "VALUES (?, ?, ?, ?, ?)",
            rows,
        )
    finally:
        con.close()
    return {
        "members": len(members), "direct": direct, "by_slug": by_slug, "name_matched": matched,
        "ambiguous": ambiguous, "unresolved": unresolved,
        "resolved_total": direct + by_slug + matched,
    }


def resolved_members() -> list[dict]:
    """(slug, name, symbol, source, ambiguous) rows that got a ticker."""
    con = _connect()
    try:
        rows = con.execute(
            "SELECT slug, name, symbol, source, ambiguous FROM universe_symbol "
            "WHERE symbol IS NOT NULL ORDER BY slug"
        ).fetchall()
    finally:
        con.close()
    return [
        {"slug": s, "name": n, "symbol": sym, "source": src, "ambiguous": amb}
        for s, n, sym, src, amb in rows
    ]


# --- price collection (archive-first for dead coins, CCXT for survivors) ------

def _store_prices(slug: str, closes: list[tuple[object, float]]) -> int:
    if not closes:
        return 0
    by_day = {day: price for day, price in closes}  # last write per UTC day wins
    con = _connect()
    try:
        con.executemany(
            "INSERT OR REPLACE INTO pit_price_history (slug, ts, price) VALUES (?, ?, ?)",
            [(slug, day, price) for day, price in by_day.items()],
        )
    finally:
        con.close()
    return len(by_day)


def _priced_slugs() -> set[str]:
    con = _connect()
    try:
        rows = con.execute("SELECT DISTINCT slug FROM pit_price_history").fetchall()
    finally:
        con.close()
    return {r[0] for r in rows}


def collect_prices(top_n: int = 80, survivor_grace_days: int = 45, resume: bool = True,
                   limit: int | None = None, only: list[str] | None = None) -> dict:
    """Price every resolved member into ``pit_price_history`` (keyed by slug).

    Identity-safe source routing: a member still ranked at the latest snapshot
    (a *survivor*) is priced CCXT-live first — same asset, full history, one fast
    call. A member that LEFT the universe (dead/departed) is priced from the
    Binance archive bounded to its [first_seen, last_seen] window, which both
    avoids the reused-ticker trap (LUNA→Terra 2.0) and keeps the request count
    bounded. Archive-miss falls through to CCXT; CCXT-miss is an accepted gap.

    ``resume`` skips members already priced. Returns a coverage summary."""
    from datetime import date, timedelta

    from quiverquant.backfill.binance_vision import archive_closes
    from quiverquant.backfill.cmc_snapshots import all_snapshot_dates
    from quiverquant.features.token_prices import fetch_daily_closes

    snaps = all_snapshot_dates()
    latest = snaps[-1] if snaps else date.today()

    members = {m["slug"]: m for m in _member_windows(top_n)}
    resolved = {r["slug"]: r for r in resolved_members()}
    already = _priced_slugs() if resume else set()

    if only:
        resolved = {s: resolved[s] for s in only if s in resolved}

    priced_ccxt = priced_archive = gaps = skipped = done = 0
    for slug, r in resolved.items():
        if limit is not None and done >= limit:
            break
        if slug in already:
            skipped += 1
            continue
        done += 1
        symbol = r["symbol"]
        win = members.get(slug)
        if win is None:
            continue
        first_seen, last_seen = win["first_seen"], win["last_seen"]
        is_survivor = (latest - last_seen).days <= survivor_grace_days

        closes: list[tuple[object, float]] = []
        source = ""
        if is_survivor:
            source, closes = fetch_daily_closes(symbol)
            if not closes:
                closes = archive_closes(f"{symbol}/USDT",
                                        first_seen.year, first_seen.month, latest.year, latest.month)
                source = "binance-archive" if closes else ""
        else:
            # bound the archive scan to the membership window (+2mo tail for the exit)
            end = last_seen + timedelta(days=60)
            closes = archive_closes(f"{symbol}/USDT",
                                    first_seen.year, first_seen.month, end.year, end.month)
            source = "binance-archive"
            if not closes:
                source, closes = fetch_daily_closes(symbol)  # never-on-Binance fallback

        n = _store_prices(slug, closes)
        if n and "archive" in source:
            priced_archive += 1
        elif n:
            priced_ccxt += 1
        else:
            gaps += 1
        tag = source or "no source"
        print(f"[pit-price] {slug:26} {symbol:8} {'surv' if is_survivor else 'dead':4} {n:5} days  {tag}")
    return {
        "resolved": len(resolved), "priced_ccxt": priced_ccxt, "priced_archive": priced_archive,
        "gaps": gaps, "skipped": skipped, "priced_total": priced_ccxt + priced_archive,
    }


def _member_windows(top_n: int) -> list[dict]:
    from quiverquant.backfill.cmc_snapshots import distinct_members

    return distinct_members(top_n=top_n)


def print_price_summary(s: dict) -> None:
    print("\n=== Point-in-time price collection ===")
    print(f"  resolved members         : {s['resolved']}")
    print(f"  priced (total)           : {s['priced_total']}  "
          f"[CCXT-live {s['priced_ccxt']}, Binance-archive {s['priced_archive']}]")
    print(f"  no price found (gap)      : {s['gaps']}")
    if s["skipped"]:
        print(f"  skipped (already priced) : {s['skipped']}")


# --- readers for the point-in-time momentum backtest --------------------------

def pit_price_df(slugs: list[str] | None = None):
    """Wide DataFrame: DATE index, one column per slug of daily USD close."""
    import pandas as pd

    con = _connect()
    try:
        q = "SELECT slug, ts, price FROM pit_price_history"
        params: list[object] = []
        if slugs:
            q += f" WHERE slug IN ({','.join('?' for _ in slugs)})"
            params = list(slugs)
        q += " ORDER BY ts"
        df = con.execute(q, params).df()
    finally:
        con.close()
    if df.empty:
        return df
    df["ts"] = pd.to_datetime(df["ts"], utc=True)
    wide = df.pivot(index="ts", columns="slug", values="price").sort_index()
    wide.index.name = "date"
    return wide


def priced_universe_at(d, top_n: int = 80) -> list[str]:
    """Slugs ranked <= ``top_n`` on the snapshot date ``d`` that ALSO have price
    data — the tradeable membership at ``d``. Joins universe_snapshot↔pit_price_history."""
    import datetime as _dt

    if isinstance(d, str):
        d = _dt.date.fromisoformat(d)
    con = _connect()
    try:
        rows = con.execute(
            "SELECT DISTINCT us.slug FROM universe_snapshot us "
            "JOIN pit_price_history p ON p.slug = us.slug "
            "WHERE us.snapshot_date = ? AND us.rank <= ? ORDER BY us.slug",
            [d, top_n],
        ).fetchall()
    finally:
        con.close()
    return [r[0] for r in rows]


def membership_series(top_n: int = 80) -> list[tuple[object, set[str]]]:
    """[(snapshot_date, {priced slugs ranked <= top_n})], ascending by date — the
    point-in-time tradeable universe at each snapshot. The backtest uses this to
    restrict each rebalance's candidate set to coins that were ACTUALLY top-N then
    (and are priceable), not today's set."""
    from quiverquant.backfill.cmc_snapshots import all_snapshot_dates

    priced = _priced_slugs()
    con = _connect()
    try:
        out = []
        for d in all_snapshot_dates():
            rows = con.execute(
                "SELECT slug FROM universe_snapshot WHERE snapshot_date = ? AND rank <= ?",
                [d, top_n],
            ).fetchall()
            members = {s for (s,) in rows if s in priced}
            if members:
                out.append((d, members))
    finally:
        con.close()
    return out


def coverage_report(top_n: int = 80) -> dict:
    """How much of each snapshot's top-N is actually priceable — the real
    usable-universe size the backtest will see, per date."""
    from quiverquant.backfill.cmc_snapshots import all_snapshot_dates

    dates = all_snapshot_dates()
    priced = _priced_slugs()
    con = _connect()
    try:
        per_date = []
        for d in dates:
            members = con.execute(
                "SELECT slug FROM universe_snapshot WHERE snapshot_date = ? AND rank <= ?",
                [d, top_n],
            ).fetchall()
            have = sum(1 for (s,) in members if s in priced)
            per_date.append((d, len(members), have))
    finally:
        con.close()
    if not per_date:
        return {"dates": 0}
    fracs = [have / tot for _, tot, have in per_date if tot]
    return {
        "dates": len(per_date),
        "median_priced_per_snapshot": sorted(h for _, _, h in per_date)[len(per_date) // 2],
        "min_priced": min(h for _, _, h in per_date),
        "max_priced": max(h for _, _, h in per_date),
        "avg_coverage_pct": round(100 * sum(fracs) / len(fracs), 1),
        "per_date": per_date,
    }


def print_resolution_summary(s: dict) -> None:
    print("\n=== Point-in-time universe symbol resolution ===")
    print(f"  members ever in top-N        : {s['members']}")
    print(f"  resolved to a ticker         : {s['resolved_total']} "
          f"({100 * s['resolved_total'] // max(s['members'], 1)}%)")
    print(f"    - direct (had CMC symbol)  : {s['direct']}")
    print(f"    - by slug==CoinGecko id    : {s['by_slug']}")
    print(f"    - matched via CoinGecko name: {s['name_matched']}  (of which ambiguous: {s['ambiguous']})")
    print(f"  unresolved (no match)        : {s['unresolved']}")
    print("\n  ambiguous = >1 CoinGecko coin shared the normalized name; ticker is best-effort.")
