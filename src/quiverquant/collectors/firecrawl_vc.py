"""Firecrawl VC-portfolio collector — the Phase 2 §3 scrape gap-filler.

VC / "smart money" portfolio pages (a16z crypto, Paradigm, Multicoin, Dragonfly,
Pantera) have no public API (PLAN.md §3, research/firecrawl.md §4) — they're plain
web pages, slow-changing, and answer "which fund is backing which project". This
collector scrapes each one through Firecrawl's `/scrape` JSON-extraction endpoint
and yields one `vc_portfolio_backing` row per (fund, company) pair. Those rows are
what finally populate the FundBacksProtocol graph edges the node-only Phase 2
migration left empty.

Firecrawl specifics we build around (research/firecrawl.md):
  * v2 REST at api.firecrawl.dev/v2 — v1 examples are stale.
  * Keyless usage is allowed for `/scrape` (per-IP rate-limited); a real
    FIRECRAWL_API_KEY (fc-...) lifts the limits. Key is optional here — send the
    bearer header only when it's set.
  * JSON/schema extraction costs ~5 credits/page vs 1 for plain markdown, so we
    scrape a small, fixed set of pages on a bi-weekly-ish cadence, not a crawl.
  * Portfolio membership is a slowly-changing fact, so we dedupe against already-
    stored (fund, company) pairs — re-scraping should only append genuinely new
    backings, not the same ~200 companies every run (mirrors whale_alert/dune).

This is an LLM-extraction scrape of pages with no SLA: treat missing/renamed
pages as a per-fund soft failure (log + skip), never a run-killer.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable

import requests

from quiverquant.collectors.base import Collector
from quiverquant.config import get_source
from quiverquant.storage import get_connection

FIRECRAWL_SCRAPE_URL = "https://api.firecrawl.dev/v2/scrape"

# The funds to track. `kind` feeds RegisterFund; all of these are venture funds.
# URLs verified against research/firecrawl.md §4 — re-check if a scrape starts
# returning zero companies (portfolio pages get restructured).
FUNDS: list[dict[str, str]] = [
    {"name": "a16z crypto", "url": "https://a16zcrypto.com/portfolio/", "kind": "VC"},
    {"name": "Paradigm", "url": "https://www.paradigm.xyz/portfolio", "kind": "VC"},
    {"name": "Multicoin Capital", "url": "https://multicoin.capital/portfolio/", "kind": "VC"},
    {"name": "Dragonfly", "url": "https://www.dragonfly.xyz/portfolio", "kind": "VC"},
    {"name": "Pantera Capital", "url": "https://panteracapital.com/portfolio/", "kind": "VC"},
]

# Schema handed to Firecrawl's extractor. Kept deliberately shallow — name is the
# only field we require; category/description are best-effort colour.
_EXTRACT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "companies": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "category": {"type": "string"},
                    "description": {"type": "string"},
                },
                "required": ["name"],
            },
        }
    },
    "required": ["companies"],
}

_EXTRACT_PROMPT = (
    "This is a venture-capital firm's portfolio page. Extract every portfolio "
    "company / project listed. For each, return its name and, if shown, its "
    "sector/category and a one-line description. Return companies only — skip "
    "the firm's own team, jobs, and navigation."
)


class FirecrawlVCCollector(Collector):
    name = "firecrawl"

    def __init__(self, company_limit: int = 120, timeout: int = 120):
        #: cap companies kept per fund (defensive: a mis-scrape shouldn't dump
        #: a whole nav tree into raw_signals).
        self.company_limit = company_limit
        self.timeout = timeout

    def fetch(self, tier: str) -> Iterable[dict[str, Any]]:
        api_key = get_source(self.name).active_key()  # None => keyless
        now = datetime.now(timezone.utc)
        seen = _stored_backings()
        for fund in FUNDS:
            data = self._scrape(fund["url"], api_key)
            if data is None:
                continue
            for company in _companies_from_response(data)[: self.company_limit]:
                cname = (company.get("name") or "").strip()
                if not cname:
                    continue
                if (fund["name"], cname.lower()) in seen:
                    continue
                seen.add((fund["name"], cname.lower()))
                yield {
                    "signal_type": "vc_portfolio_backing",
                    "entity": cname,
                    "ts": now,
                    "payload": {
                        "fund_name": fund["name"],
                        "fund_kind": fund["kind"],
                        "company_name": cname,
                        "category": (company.get("category") or "").strip() or None,
                        "description": (company.get("description") or "").strip() or None,
                        "round": None,           # portfolio pages rarely state the round
                        "source_url": fund["url"],
                    },
                }

    def _scrape(self, url: str, api_key: str | None) -> dict[str, Any] | None:
        """POST one page to Firecrawl /scrape with JSON extraction. Returns the
        parsed response `data` dict, or None on any failure (logged, non-fatal)."""
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        body = {
            "url": url,
            "onlyMainContent": True,
            "formats": [
                {"type": "json", "prompt": _EXTRACT_PROMPT, "schema": _EXTRACT_SCHEMA}
            ],
        }
        try:
            resp = requests.post(
                FIRECRAWL_SCRAPE_URL, json=body, headers=headers, timeout=self.timeout
            )
        except requests.RequestException as exc:  # network/timeout — skip this fund
            print(f"  firecrawl: {url} request failed: {exc}")
            return None
        if resp.status_code != 200:
            # 402 = out of credits, 401 = bad/absent key on a keyed route,
            # 429 = rate-limited. All are "skip this page", not crash.
            print(f"  firecrawl: {url} -> HTTP {resp.status_code} {resp.text[:160]}")
            return None
        payload = resp.json() if resp.content else {}
        if not payload.get("success", True):
            print(f"  firecrawl: {url} -> success=false {str(payload)[:160]}")
            return None
        return payload.get("data") or {}


def _companies_from_response(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Pull the company list out of a Firecrawl scrape `data` block. The extracted
    object lives under `json` in v2; tolerate a couple of shapes so a minor API
    tweak doesn't silently zero this out."""
    extracted = data.get("json") or data.get("extract") or data.get("llm_extraction") or {}
    if isinstance(extracted, dict):
        companies = extracted.get("companies")
        if isinstance(companies, list):
            return [c for c in companies if isinstance(c, dict)]
    return []


def _stored_backings() -> set[tuple[str, str]]:
    """Already-stored (fund_name, lower(company_name)) pairs, so re-scrapes only
    append new backings. Portfolio membership is slowly-changing, not a time
    series — re-inserting identical pairs would be pure waste."""
    con = get_connection()
    try:
        rows = con.execute(
            "SELECT DISTINCT "
            "  json_extract_string(payload, '$.fund_name'), "
            "  lower(json_extract_string(payload, '$.company_name')) "
            "FROM raw_signals WHERE source = 'firecrawl' "
            "  AND signal_type = 'vc_portfolio_backing'"
        ).fetchall()
    finally:
        con.close()
    return {(f, c) for f, c in rows if f and c}
