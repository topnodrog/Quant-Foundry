"""Resolve VC-backed company names to tradeable tokens (path 1, step A).

The VC portfolio pages give *company names*; most are equity/pre-token, and the
ones with tokens need name->ticker resolution. We match against CoinGecko's
**liquid** universe (top-N by market cap) rather than the full 17k coin list, so
generic names ("Finance", "Story", "Across") can only match a real, liquid token
instead of some micro-cap namesake — a precision-over-recall choice.

Result is cached in a ``vc_token_map`` DuckDB table so downstream steps
(OHLCV collection, the cross-sectional backtest) don't re-hit CoinGecko.

SURVIVORSHIP-BIAS WARNING: the portfolio pages list *current* holdings, so this
map only ever contains survivors. Anything built on it is an upper bound, not a
trustworthy backtest — see ``research/open-foundry-strategic-advantage.md`` and
the path-2 archive.org plan.
"""

from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass

import requests

from quiverquant.config import DATA_DIR, DB_PATH

_CG_BASE = "https://api.coingecko.com/api/v3"
_UA = {"User-Agent": "quant-foundry-research/0.1"}

# a16z category headers that were mis-scraped into company_name — never tokens.
_DENY = {"finance", "defi", "enterprise", "infrastructure", "consumer"}

_SCHEMA = """
CREATE TABLE IF NOT EXISTS vc_token_map (
    company          VARCHAR NOT NULL,
    gecko_id         VARCHAR NOT NULL,
    symbol           VARCHAR NOT NULL,
    market_cap_rank  INTEGER,
    PRIMARY KEY (company)
);
"""


@dataclass(frozen=True)
class Resolution:
    company: str
    gecko_id: str
    symbol: str
    market_cap_rank: int | None


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def _connect():
    import duckdb

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(DB_PATH))
    con.execute(_SCHEMA)
    return con


def _cg_get(path: str, params: dict, max_retries: int = 5) -> list:
    """GET with retry/backoff on CoinGecko's aggressive free-tier 429s."""
    headers = dict(_UA)
    key = os.getenv("COINGECKO_API_KEY")
    if key:
        headers["x-cg-demo-api-key"] = key
    delay = 8.0
    for attempt in range(max_retries):
        resp = requests.get(f"{_CG_BASE}{path}", params=params, headers=headers, timeout=60)
        if resp.status_code == 429:
            wait = float(resp.headers.get("Retry-After") or delay)
            if attempt == max_retries - 1:
                resp.raise_for_status()
            time.sleep(wait)
            delay *= 2  # exponential backoff
            continue
        resp.raise_for_status()
        return resp.json()
    return []


def fetch_liquid_universe(top_n: int = 1000, pause: float = 6.0) -> list[dict]:
    """Top-``top_n`` coins by market cap: ``[{id, symbol, name, market_cap_rank}]``.

    Paginates 250/page (CoinGecko's max) and paces requests for the free tier.
    On a persistent rate-limit it returns whatever it has so far rather than
    aborting — a slightly smaller universe just means slightly lower recall.
    """
    out: list[dict] = []
    per_page = 250
    pages = (top_n + per_page - 1) // per_page
    for page in range(1, pages + 1):
        try:
            batch = _cg_get(
                "/coins/markets",
                {
                    "vs_currency": "usd",
                    "order": "market_cap_desc",
                    "per_page": per_page,
                    "page": page,
                },
            )
        except requests.HTTPError as e:
            print(f"[resolve] stopping at page {page} ({e}); using {len(out)} coins so far")
            break
        if not batch:
            break
        out.extend(batch)
        if len(batch) < per_page:
            break
        if page < pages:
            time.sleep(pause)
    return out[:top_n]


def distinct_companies() -> list[str]:
    """Distinct company names from the stored VC-portfolio backings."""
    con = _connect()
    try:
        rows = con.execute(
            "SELECT DISTINCT payload->>'$.company_name' AS c FROM raw_signals "
            "WHERE signal_type = 'vc_portfolio_backing' AND c IS NOT NULL"
        ).fetchall()
    finally:
        con.close()
    return sorted({r[0] for r in rows if r[0]})


def resolve(companies: list[str], universe: list[dict]) -> list[Resolution]:
    """Normalized exact-name match of companies against the liquid universe."""
    by_name: dict[str, dict] = {}
    for c in universe:
        name = c.get("name")
        if name:
            by_name.setdefault(_norm(name), c)  # first (highest mcap) wins on dupes

    out: list[Resolution] = []
    for company in companies:
        n = _norm(company)
        if n in _DENY:
            continue
        hit = by_name.get(n)
        if hit:
            out.append(
                Resolution(
                    company=company,
                    gecko_id=hit["id"],
                    symbol=str(hit["symbol"]).upper(),
                    market_cap_rank=hit.get("market_cap_rank"),
                )
            )
    out.sort(key=lambda r: (r.market_cap_rank is None, r.market_cap_rank or 0))
    return out


def store_map(resolutions: list[Resolution]) -> int:
    con = _connect()
    try:
        con.execute("DELETE FROM vc_token_map")  # rebuilt wholesale each run
        con.executemany(
            "INSERT INTO vc_token_map (company, gecko_id, symbol, market_cap_rank) "
            "VALUES (?, ?, ?, ?)",
            [(r.company, r.gecko_id, r.symbol, r.market_cap_rank) for r in resolutions],
        )
    finally:
        con.close()
    return len(resolutions)


def read_map() -> list[Resolution]:
    con = _connect()
    try:
        rows = con.execute(
            "SELECT company, gecko_id, symbol, market_cap_rank FROM vc_token_map "
            "ORDER BY market_cap_rank NULLS LAST"
        ).fetchall()
    finally:
        con.close()
    return [Resolution(company=c, gecko_id=g, symbol=s, market_cap_rank=r) for c, g, s, r in rows]


def build_map(top_n: int = 1500) -> list[Resolution]:
    """Fetch the liquid universe, resolve stored companies, cache and return."""
    universe = fetch_liquid_universe(top_n=top_n)
    resolutions = resolve(distinct_companies(), universe)
    store_map(resolutions)
    return resolutions


def print_map(resolutions: list[Resolution], total_companies: int | None = None) -> None:
    print("\n=== VC name -> token resolution (liquid universe) ===")
    if total_companies:
        pct = 100 * len(resolutions) // max(total_companies, 1)
        print(f"  resolved {len(resolutions)}/{total_companies} companies ({pct}%) to a liquid token")
    else:
        print(f"  resolved {len(resolutions)} companies to a liquid token")
    print(f"\n  {'company':24} {'symbol':8} {'mcap_rank':>9}  gecko_id")
    for r in resolutions:
        rank = "n/a" if r.market_cap_rank is None else str(r.market_cap_rank)
        print(f"  {r.company:24} {r.symbol:8} {rank:>9}  {r.gecko_id}")
    print("\n  WARNING: current-holdings snapshot -> survivorship-biased; upper bound only.")
