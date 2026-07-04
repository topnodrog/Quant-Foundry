"""SEC EDGAR full-text search + enforcement RSS. Free, public, no key.
PLAN.md §2 #6.

SEC requires a descriptive User-Agent identifying the requester (fair-access
policy, enforced — unset/generic UAs get 403s), so every request here sends
one. Litigation-release RSS moved off `/rss/litigation/litreleases.xml`
(404) to `/enforcement-litigation/litigation-releases/rss` — verified live
2026-07-02; PLAN.md's URL was stale.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable

import feedparser
import requests

from quiverquant.collectors.base import Collector

USER_AGENT = "QuiverQuant Research james_gordon@junctiongenerator.net"
FULLTEXT_SEARCH = "https://efts.sec.gov/LATEST/search-index"
LITIGATION_RSS = "https://www.sec.gov/enforcement-litigation/litigation-releases/rss"
ADMIN_PROCEEDINGS_RSS = "https://www.sec.gov/enforcement-litigation/administrative-proceedings/rss"

DEFAULT_QUERIES = ["crypto asset", "digital asset securities", "cryptocurrency"]


class SecEdgarCollector(Collector):
    name = "sec_edgar"

    def __init__(self, queries: list[str] | None = None, hits_per_query: int = 10):
        self.queries = queries or DEFAULT_QUERIES
        self.hits_per_query = hits_per_query

    def fetch(self, tier: str) -> Iterable[dict[str, Any]]:
        yield from self._fetch_fulltext_search()
        yield from self._fetch_rss(LITIGATION_RSS, "litigation_release")
        yield from self._fetch_rss(ADMIN_PROCEEDINGS_RSS, "administrative_proceeding")

    def _fetch_fulltext_search(self) -> Iterable[dict[str, Any]]:
        headers = {"User-Agent": USER_AGENT}
        for query in self.queries:
            resp = requests.get(
                FULLTEXT_SEARCH,
                params={"q": f'"{query}"'},
                headers=headers,
                timeout=30,
            )
            if resp.status_code != 200:
                continue
            hits = resp.json().get("hits", {}).get("hits", [])
            for hit in hits[: self.hits_per_query]:
                src = hit.get("_source", {})
                filed = src.get("file_date") or src.get("period_ending")
                ts = _parse_date(filed)
                yield {
                    "signal_type": "fulltext_filing_match",
                    "entity": ",".join(src.get("ciks", []) or []) or None,
                    "ts": ts,
                    "payload": {
                        "query": query,
                        "display_names": src.get("display_names"),
                        "form_type": src.get("root_forms") or src.get("file_type"),
                        "file_date": filed,
                        "adsh": hit.get("_id"),
                    },
                }

    def _fetch_rss(self, url: str, signal_type: str) -> Iterable[dict[str, Any]]:
        headers = {"User-Agent": USER_AGENT}
        resp = requests.get(url, headers=headers, timeout=30)
        if resp.status_code != 200:
            return
        parsed = feedparser.parse(resp.content)
        for entry in parsed.entries:
            ts = _parse_struct_time(entry.get("published_parsed"))
            yield {
                "signal_type": signal_type,
                "entity": entry.get("title"),
                "ts": ts,
                "payload": {
                    "title": entry.get("title"),
                    "link": entry.get("link"),
                    "summary": entry.get("summary"),
                },
            }


def _parse_date(value: str | None) -> datetime:
    if not value:
        return datetime.now(timezone.utc)
    try:
        return datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError:
        return datetime.now(timezone.utc)


def _parse_struct_time(value) -> datetime:
    if not value:
        return datetime.now(timezone.utc)
    return datetime(*value[:6], tzinfo=timezone.utc)
