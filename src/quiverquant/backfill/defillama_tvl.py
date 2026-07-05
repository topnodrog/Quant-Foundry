"""Historical DeFi TVL backfill from DefiLlama.

The live ``defillama`` collector stores a single current ``tvl_snapshot`` per
protocol — no history, so not backtestable. This pulls each protocol's full
daily TVL series from ``/protocol/{slug}`` (free, no key) and stores it as
``tvl_history`` rows in ``raw_signals``, deduped by (protocol, day) so repeated
backfills are idempotent.

CEX entries dominate DefiLlama's TVL ranking but their "TVL" is exchange
reserves, not DeFi locked value — excluded by default so the signal stays
DeFi-native.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import requests

from quiverquant.storage import get_connection, insert_signals

BASE = "https://api.llama.fi"
SIGNAL_TYPE = "tvl_history"
_DEFAULT_EXCLUDED = ("CEX",)


def select_top_protocols(
    n: int, exclude_categories: tuple[str, ...] = _DEFAULT_EXCLUDED
) -> list[dict[str, Any]]:
    """Return metadata for the top-``n`` protocols by current TVL."""
    resp = requests.get(f"{BASE}/protocols", timeout=30)
    resp.raise_for_status()
    protocols = [
        p for p in resp.json() if p.get("category") not in exclude_categories
    ]
    protocols.sort(key=lambda p: (p.get("tvl") or 0), reverse=True)
    out: list[dict[str, Any]] = []
    for p in protocols[:n]:
        slug = p.get("slug")
        if slug:
            out.append(
                {
                    "slug": slug,
                    "name": p.get("name"),
                    "category": p.get("category"),
                    "chain": p.get("chain"),
                }
            )
    return out


def fetch_protocol_history(slug: str) -> list[dict[str, Any]]:
    """Return a protocol's daily ``[{date, totalLiquidityUSD}]`` series."""
    resp = requests.get(f"{BASE}/protocol/{slug}", timeout=60)
    if resp.status_code != 200:
        return []
    return resp.json().get("tvl") or []


def _seen_days(entity: str) -> set[str]:
    con = get_connection()
    try:
        rows = con.execute(
            "SELECT DISTINCT CAST(ts AS DATE) FROM raw_signals "
            "WHERE signal_type = ? AND entity = ?",
            [SIGNAL_TYPE, entity],
        ).fetchall()
    finally:
        con.close()
    return {r[0].isoformat() for r in rows if r[0]}


def history_to_records(
    slug: str,
    meta: dict[str, Any],
    history: list[dict[str, Any]],
    seen_days: set[str],
    since: datetime | None = None,
) -> list[dict[str, Any]]:
    """Pure map: DefiLlama ``[{date, totalLiquidityUSD}]`` -> raw_signals records.

    Drops points missing a date/TVL, points before ``since``, and any date
    already in ``seen_days`` (also dedupes duplicate dates within one response).
    """
    seen = set(seen_days)
    records: list[dict[str, Any]] = []
    for point in history:
        date = point.get("date")
        tvl = point.get("totalLiquidityUSD")
        if date is None or tvl is None:
            continue
        ts = datetime.fromtimestamp(int(date), tz=timezone.utc)
        if since is not None and ts < since:
            continue
        day = ts.date().isoformat()
        if day in seen:
            continue
        seen.add(day)
        records.append(
            {
                "source": "defillama",
                "signal_type": SIGNAL_TYPE,
                "entity": slug,
                "ts": ts,
                "tier": "free",
                "payload": {
                    "tvl": float(tvl),
                    "name": meta.get("name"),
                    "category": meta.get("category"),
                    "chain": meta.get("chain"),
                    "date": day,
                },
            }
        )
    return records


def backfill_tvl_history(
    top: int = 25,
    slugs: list[str] | None = None,
    since: datetime | None = None,
) -> int:
    """Backfill daily TVL history for the top-``top`` protocols (or explicit
    ``slugs``). ``since`` clips to points on/after that date. Returns rows added.
    """
    if slugs:
        protocols: list[dict[str, Any]] = [
            {"slug": s, "name": None, "category": None, "chain": None} for s in slugs
        ]
    else:
        protocols = select_top_protocols(top)

    total = 0
    for meta in protocols:
        slug = meta["slug"]
        history = fetch_protocol_history(slug)
        records = history_to_records(slug, meta, history, _seen_days(slug), since)
        added = insert_signals(records)
        total += added
        print(f"[defillama-tvl] {slug}: +{added} points ({len(history)} available)")
    return total
