"""Point-in-time VC portfolios from the Wayback Machine (path 2).

Path 1's cross-sectional book was survivorship-biased: the *current* portfolio
pages only list survivors. archive.org has historical captures of those same pages,
so enumerating snapshots over time reconstructs **who was backed, and when** —
including projects that later died. That's the only free way to defeat the
survivorship bias baked into the VC-conviction signal.

Two moving parts, and a feasibility gate between them:
1. **CDX enumeration** (this module, solid) — the Wayback CDX API lists every
   capture of a URL with its timestamp; keyless and reliable.
2. **Extraction** (hard, gated) — pulling the company list out of an archived page.
   Modern VC sites are client-rendered SPAs whose archived HTML is often *empty of
   content*, so before building a real extractor we ``probe`` one snapshot and check
   whether known companies even appear in the raw HTML. If they don't, we need a
   different capture (older pre-SPA snapshots, or the site's JSON/API the page calls).
"""

from __future__ import annotations

import html as _htmllib
import re
from dataclasses import dataclass

import requests

from quiverquant.storage import insert_signals

_CDX = "http://web.archive.org/cdx/search/cdx"
_UA = {"User-Agent": "quant-foundry-research/0.1"}

# VC portfolio pages to reconstruct (start with the two that dominated path 1's data).
VC_PORTFOLIO_URLS = {
    "a16z crypto": "a16zcrypto.com/portfolio/",
    "Paradigm": "paradigm.xyz/portfolio",
}

# Known real portfolio companies — a cheap oracle for "did extraction find anything?".
_KNOWN = ["Uniswap", "Coinbase", "OpenSea", "Optimism", "dYdX", "Compound", "Lido", "Aztec"]


@dataclass(frozen=True)
class Snapshot:
    timestamp: str  # yyyymmddhhmmss
    original: str
    status: str

    @property
    def date(self) -> str:
        t = self.timestamp
        return f"{t[0:4]}-{t[4:6]}-{t[6:8]}"

    @property
    def raw_url(self) -> str:
        # the `id_` modifier returns the archived bytes without Wayback's injected toolbar
        return f"https://web.archive.org/web/{self.timestamp}id_/{self.original}"


def list_snapshots(
    url: str,
    from_year: int = 2020,
    to_year: int = 2026,
    collapse: str = "timestamp:6",  # 6 digits = yyyymm -> ~one capture per month
) -> list[Snapshot]:
    """Enumerate Wayback captures of ``url`` (HTTP 200s only), ~monthly."""
    params = {
        "url": url,
        "output": "json",
        "from": str(from_year),
        "to": str(to_year),
        "collapse": collapse,
        "filter": "statuscode:200",
    }
    resp = requests.get(_CDX, params=params, headers=_UA, timeout=60)
    resp.raise_for_status()
    rows = resp.json()
    if not rows or len(rows) < 2:
        return []
    header = rows[0]
    ci = {name: i for i, name in enumerate(header)}
    out: list[Snapshot] = []
    for r in rows[1:]:
        out.append(
            Snapshot(
                timestamp=r[ci["timestamp"]],
                original=r[ci["original"]],
                status=r[ci.get("statuscode", 4)],
            )
        )
    return out


def fetch_snapshot(snap: Snapshot, max_retries: int = 3) -> str:
    """Fetch the archived raw HTML for a snapshot, retrying archive.org's frequent
    transient connection refusals / timeouts with backoff."""
    import time

    delay = 3.0
    last_err: Exception | None = None
    for attempt in range(max_retries):
        try:
            resp = requests.get(snap.raw_url, headers=_UA, timeout=90)
            resp.raise_for_status()
            return resp.text
        except requests.RequestException as e:
            last_err = e
            if attempt < max_retries - 1:
                time.sleep(delay)
                delay *= 2
    raise last_err  # type: ignore[misc]


# Portfolio companies render as external-link anchors. We key off the stable
# link attributes (target/rel/external href), NOT the Tailwind class names, which
# churn between site redesigns. Older pre-redesign snapshots use different markup
# and simply extract nothing (skipped) — coverage spans the current-design era.
_ANCHOR = re.compile(r'<a\b[^>]*\btarget="_blank"[^>]*\bhref="([^"]+)"[^>]*>(.*?)</a>', re.DOTALL | re.I)
_TAG = re.compile(r"<[^>]+>")
_SKIP_HREF = (
    "a16z", "paradigm.xyz", "twitter.com", "x.com", "linkedin", "facebook",
    "youtube", "instagram", "archive.org", "mailto:", "t.me", "discord", "medium.com",
)


def extract_companies(html: str) -> dict[str, str]:
    """Company name -> external URL from an archived portfolio page (best-effort)."""
    out: dict[str, str] = {}
    for href, inner in _ANCHOR.findall(html):
        if not href.startswith("http") or any(s in href.lower() for s in _SKIP_HREF):
            continue
        name = _htmllib.unescape(_TAG.sub("", inner)).strip()
        if name and len(name) <= 40:
            out.setdefault(name, href)
    return out


def collect_point_in_time(fund: str, from_year: int = 2020, to_year: int = 2026, pause: float = 2.0) -> dict:
    """Walk every monthly snapshot of ``fund``'s portfolio page, extract its
    companies, and record each company's first/last-seen dates + snapshot count.

    Stores one ``vc_portfolio_pit`` row per (fund, company) and returns a summary
    including the survivorship-bias payoff: companies present in an earlier snapshot
    but ABSENT from the latest extractable one (i.e. churned out — the names a
    current-only scrape silently drops).
    """
    url = VC_PORTFOLIO_URLS[fund]
    snaps = list_snapshots(url, from_year=from_year, to_year=to_year)

    import time

    # company -> {first, last, count}
    seen: dict[str, dict] = {}
    extractable_dates: list[str] = []
    for i, snap in enumerate(snaps):
        if i > 0:
            time.sleep(pause)  # pace to avoid archive.org rate-limiting
        try:
            companies = extract_companies(fetch_snapshot(snap))
        except Exception as e:  # noqa: BLE001 - one bad snapshot shouldn't abort
            print(f"[wayback] {snap.date} fetch failed ({type(e).__name__})")
            continue
        if not companies:
            continue  # old-format / empty snapshot
        extractable_dates.append(snap.date)
        for name, href in companies.items():
            rec = seen.setdefault(name, {"first": snap.date, "last": snap.date, "count": 0, "url": href})
            rec["first"] = min(rec["first"], snap.date)
            rec["last"] = max(rec["last"], snap.date)
            rec["count"] += 1
        print(f"[wayback] {snap.date}: {len(companies)} companies")

    if not extractable_dates:
        return {"fund": fund, "snapshots_total": len(snaps), "snapshots_extractable": 0,
                "companies": 0, "churned_out": []}

    latest = max(extractable_dates)
    churned = sorted(n for n, r in seen.items() if r["last"] < latest)

    records = [
        {
            "source": "wayback_vc",
            "tier": "free",
            "signal_type": "vc_portfolio_pit",
            "entity": name,
            "ts": _date_to_dt(r["first"]),
            "payload": {
                "fund": fund, "company": name, "url": r["url"],
                "first_seen": r["first"], "last_seen": r["last"],
                "snapshot_count": r["count"], "still_present": r["last"] == latest,
            },
        }
        for name, r in seen.items()
    ]
    inserted = insert_signals(records)

    return {
        "fund": fund,
        "snapshots_total": len(snaps),
        "snapshots_extractable": len(extractable_dates),
        "date_range": f"{min(extractable_dates)} .. {latest}",
        "companies": len(seen),
        "rows_inserted": inserted,
        "churned_out": churned,
    }


def _date_to_dt(date_str: str):
    from datetime import datetime, timezone

    return datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)


def probe_extractable(html: str) -> dict:
    """Cheap feasibility check: does the archived HTML actually contain company
    names, or is it an empty SPA shell? Looks for known portfolio companies and
    for any embedded JSON payload the page might hydrate from."""
    found = [name for name in _KNOWN if name.lower() in html.lower()]
    has_next_data = "__NEXT_DATA__" in html or "application/json" in html
    return {
        "html_len": len(html),
        "known_companies_found": found,
        "n_known_found": len(found),
        "looks_like_spa_json": has_next_data,
        "verdict": (
            "content present in HTML" if len(found) >= 3
            else "likely empty SPA shell — needs JSON/API or older snapshot"
        ),
    }
