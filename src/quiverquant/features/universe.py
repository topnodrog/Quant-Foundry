"""Broad liquid-alt universe for cross-sectional strategies (option 1).

The Phase-4 gates showed no BTC daily-timing edge in any single free signal or their
ensemble. The evidence says change the target: cross-sectional selection (rank many
coins, hold the best) is where free signals more plausibly carry edge. This module
assembles the universe — top-N coins by market cap (CoinGecko), minus stablecoins,
BTC (the benchmark), and wrapped/staked derivatives — and pulls their daily prices
via CCXT into the shared ``token_price_history`` table, recording membership in
``universe_token`` so the momentum backtest knows what's tradeable.

SURVIVORSHIP CAVEAT (same as path 1): this is *today's* liquid set, so coins that
died are absent — an upper bound. A clean version needs point-in-time universe
membership. Cross-sectional momentum is less exposed than "buy-and-hold the basket"
(it rebalances, and the null is random selection from the same biased set), but the
bias is real; results are directional, not gospel.
"""

from __future__ import annotations

from quiverquant.config import DATA_DIR, DB_PATH
from quiverquant.features.token_prices import cache_prices, fetch_daily_closes
from quiverquant.features.token_resolve import fetch_liquid_universe

# Non-tradeable-as-alpha: stablecoins, BTC (benchmark), wrapped/staked mirrors,
# tokenized treasuries/money-market funds, and gold trackers.
_EXCLUDE = {
    "BTC", "USDT", "USDC", "DAI", "BUSD", "TUSD", "FDUSD", "USDS", "USDE", "PYUSD",
    "USD1", "USDD", "GUSD", "WBTC", "WETH", "WEETH", "WBETH", "STETH", "WSTETH",
    "RETH", "CBETH", "SUSDE", "BSC-USD", "LEO",
    "USDG", "USDY", "USDF", "RLUSD", "USYC", "USTB", "BUIDL", "EUTBL", "BFUSD",
    "USDGO", "JTRSY", "STABLE", "USDX", "XAUT", "PAXG",
}

_SCHEMA = """
CREATE TABLE IF NOT EXISTS universe_token (
    gecko_id         VARCHAR NOT NULL,
    symbol           VARCHAR NOT NULL,
    market_cap_rank  INTEGER,
    PRIMARY KEY (gecko_id)
);
"""


def _connect():
    import duckdb

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(DB_PATH))
    con.execute(_SCHEMA)
    return con


def read_universe_ids() -> list[str]:
    con = _connect()
    try:
        rows = con.execute(
            "SELECT gecko_id FROM universe_token ORDER BY market_cap_rank NULLS LAST"
        ).fetchall()
    finally:
        con.close()
    return [r[0] for r in rows]


def collect_universe(top_n: int = 80, min_days: int = 120, resume: bool = False) -> dict:
    """Fetch the top-``top_n`` liquid coins (minus excludes), pull daily prices via
    CCXT, and record membership. Returns a summary. Soft-fails coins not on a CEX.

    ``min_days`` drops just-listed coins (e.g. 5 days of history) that could never
    survive a lookback anyway and only pollute the universe/price tables.

    ``resume`` keeps already-collected members and only fetches the missing coins —
    venues rate-ban mid-run on a cold IP, so the practical path to a full universe
    is one initial run plus resumed retries, not one giant pull.
    """
    liquid = fetch_liquid_universe(top_n=top_n)
    con = _connect()
    try:
        if resume:
            have = {r[0] for r in con.execute("SELECT gecko_id FROM universe_token").fetchall()}
        else:
            con.execute("DELETE FROM universe_token")
            have = set()

        kept, priced, skipped = 0, 0, []
        for c in liquid:
            symbol = str(c.get("symbol", "")).upper()
            gid = c.get("id")
            if not symbol or not gid or symbol in _EXCLUDE:
                continue
            if gid in have:
                n = con.execute(
                    "SELECT count(*) FROM token_price_history WHERE gecko_id = ?", [gid]
                ).fetchone()[0]
                kept += 1
                priced += n
                print(f"[universe] {symbol:10} {n:5} days  (cached)")
                continue
            source, closes = fetch_daily_closes(symbol)
            if len(closes) < min_days:
                skipped.append(symbol)
                continue
            cache_prices(gid, closes)
            con.execute(
                "INSERT OR REPLACE INTO universe_token (gecko_id, symbol, market_cap_rank) "
                "VALUES (?, ?, ?)",
                [gid, symbol, c.get("market_cap_rank")],
            )
            kept += 1
            priced += len(closes)
            print(f"[universe] {symbol:10} {len(closes):5} days  {source}")
    finally:
        con.close()
    return {"universe_size": kept, "price_rows": priced, "skipped": skipped}
