"""Perigon news-intelligence API client + a budget-aware lookback probe.

Perigon is the news/sentiment source (PLAN.md §2 #4 — the category we're weakest
in, having only the coarse market-wide Fear & Greed index). The plan lives in
``research/perigon-plan.md``. The hard constraint is **150 API calls/month**, so
this module is deliberately thin and every call is deliberate.

The main article-search endpoint is ``GET https://api.perigon.io/v1/all`` with the
key passed as an ``apiKey`` query param. Responses are parsed defensively (``.get``
everywhere) because the exact JSON shape is confirmed against a live call, not from
the (JS-rendered) docs — see ``probe`` below, which is designed to be the very
first call you spend: it verifies the key AND measures how far back this plan's
history reaches, which decides whether Perigon can backfill a series or only
accumulate one going forward.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Iterable

import requests

from quiverquant.collectors.base import Collector
from quiverquant.config import get_source
from quiverquant.storage import get_connection

_BASE = "https://api.perigon.io/v1"

# Perigon's own "Cryptocurrency" topic — verified as the dominant topic on a broad
# crypto query (57/100), while noise ("World Cup", "Royal Family", "DevOps") carried
# other topics. Filtering by topic is far cleaner than a loose keyword OR.
CRYPTO_TOPIC = "Cryptocurrency"


class PerigonError(RuntimeError):
    pass


def _api_key() -> str:
    key = get_source("perigon").active_key()
    if not key:
        raise PerigonError(
            "PERIGON_API_KEY not set - add it to .env (see .env.example). "
            "Perigon has no keyless tier."
        )
    return key


def search_all(
    q: str | None = None,
    frm: str | None = None,
    to: str | None = None,
    size: int = 100,
    page: int = 0,
    sort_by: str = "date",
    extra: dict[str, Any] | None = None,
) -> dict:
    """One call to ``/v1/all``. ``frm``/``to`` are yyyy-mm-dd publish-date bounds.

    ``size`` maxes at 100 (articles per call — maximise it, calls are the scarce
    resource, not articles). Returns the raw parsed JSON dict.
    """
    params: dict[str, Any] = {"apiKey": _api_key(), "size": min(size, 100), "page": page, "sortBy": sort_by}
    if q:
        params["q"] = q
    if frm:
        params["from"] = frm
    if to:
        params["to"] = to
    if extra:
        params.update(extra)

    resp = requests.get(f"{_BASE}/all", params=params, timeout=60)
    if resp.status_code == 401:
        raise PerigonError("401 Unauthorized — check PERIGON_API_KEY is correct")
    if resp.status_code == 429:
        raise PerigonError("429 Too Many Requests — monthly call budget likely exhausted")
    if resp.status_code >= 400:
        # Don't raise_for_status(): its message embeds the full request URL,
        # apiKey query param included, and the scheduled task logs stderr to
        # data/news_cron.log — keep the key out of that file.
        raise PerigonError(f"HTTP {resp.status_code} from Perigon /all: {resp.text[:200]}")
    return resp.json()


def _articles(data: dict) -> list[dict]:
    """Pull the article list out of whatever key Perigon uses (defensive)."""
    for k in ("articles", "results", "data"):
        v = data.get(k)
        if isinstance(v, list):
            return v
    return []


def _pub_date(article: dict) -> str | None:
    for k in ("pubDate", "publishedAt", "date", "addDate"):
        v = article.get(k)
        if v:
            return str(v)
    return None


def _net_sentiment(article: dict) -> float | None:
    s = article.get("sentiment")
    if isinstance(s, dict):
        return round(float(s.get("positive", 0) or 0) - float(s.get("negative", 0) or 0), 4)
    return None


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        try:
            return datetime.strptime(value[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError:
            return None


class PerigonNewsCollector(Collector):
    """Incremental crypto-news feed — 'report future news as it comes in'.

    Each run pulls crypto articles published since the newest one we've already
    stored (falling back to a short lookback on first run), dedupes by
    ``articleId``, and stores one ``crypto_news`` row per new article with its
    per-article sentiment. Budget: **one API call per run** (up to 100 articles);
    schedule it daily and it accumulates a real sentiment time series over time.
    """

    name = "perigon"

    def __init__(self, size: int = 100, default_lookback_days: int = 2) -> None:
        self.size = size
        self.default_lookback_days = default_lookback_days

    def fetch(self, tier: str) -> Iterable[dict[str, Any]]:
        since = _latest_news_date() or (
            datetime.now(timezone.utc) - timedelta(days=self.default_lookback_days)
        )
        frm = since.date().isoformat()
        to = (datetime.now(timezone.utc) + timedelta(days=1)).date().isoformat()
        data = search_all(
            frm=frm, to=to, size=self.size, sort_by="date", extra={"topic": CRYPTO_TOPIC}
        )

        seen = _stored_article_ids()
        for a in _articles(data):
            aid = a.get("articleId") or a.get("url")
            if not aid or aid in seen:
                continue
            seen.add(aid)
            ts = _parse_dt(_pub_date(a))
            if ts is None:
                continue
            src = a.get("source")
            src_name = src.get("name") or src.get("domain") if isinstance(src, dict) else src
            yield {
                "signal_type": "crypto_news",
                "entity": src_name,
                "ts": ts,
                "payload": {
                    "articleId": aid,
                    "title": a.get("title"),
                    "url": a.get("url"),
                    "source": src_name,
                    "pubDate": _pub_date(a),
                    "net_sentiment": _net_sentiment(a),
                    "sentiment": a.get("sentiment"),
                    "topics": [t.get("name") for t in (a.get("topics") or []) if isinstance(t, dict)],
                },
            }


def _iter_months(start: str, end: str):
    """Yield (year, month) from ``start`` (YYYY-MM) up to but excluding ``end``."""
    sy, sm = (int(x) for x in start.split("-"))
    ey, em = (int(x) for x in end.split("-"))
    y, m = sy, sm
    while (y, m) < (ey, em):
        yield y, m
        m += 1
        if m > 12:
            y, m = y + 1, 1


def _stored_sentiment_months() -> set[str]:
    con = get_connection()
    try:
        rows = con.execute(
            "SELECT DISTINCT json_extract_string(payload, '$.month') "
            "FROM raw_signals WHERE signal_type = 'news_sentiment'"
        ).fetchall()
    finally:
        con.close()
    return {r[0] for r in rows if r[0]}


def backfill_monthly_sentiment(start: str = "2022-01", end: str = "2026-07", size: int = 100) -> int:
    """Backfill a monthly crypto-news sentiment series (ONE Perigon call/month).

    For each month, samples up to ``size`` articles, averages their net sentiment,
    and stores one ``news_sentiment`` point **stamped at the first day of the NEXT
    month** — so a backtest only learns month M's sentiment once M has closed (no
    lookahead). Skips months already stored, so it's safe to resume.
    """
    have = _stored_sentiment_months()
    records: list[dict[str, Any]] = []
    for y, m in _iter_months(start, end):
        month = f"{y}-{m:02d}"
        if month in have:
            continue
        frm = f"{month}-01"
        ny, nm = (y + 1, 1) if m == 12 else (y, m + 1)
        to = f"{ny}-{nm:02d}-01"
        data = search_all(frm=frm, to=to, size=size, sort_by="date", extra={"topic": CRYPTO_TOPIC})
        arts = _articles(data)
        nets = [s for a in arts if (s := _net_sentiment(a)) is not None]
        net = round(sum(nets) / len(nets), 4) if nets else None
        num = next((data.get(k) for k in ("numResults", "total") if k in data), None)
        print(f"[sentiment] {month}: {len(arts)} articles, net {net}, numResults {num}")
        records.append({
            "source": "perigon",
            "tier": "free",
            "signal_type": "news_sentiment",
            "entity": "market",
            "ts": datetime(ny, nm, 1, tzinfo=timezone.utc),
            "payload": {
                "month": month, "net_sentiment": net,
                "article_count": len(arts), "num_results": num,
            },
        })
    from quiverquant.storage import insert_signals

    return insert_signals(records)


def _latest_news_date() -> datetime | None:
    con = get_connection()
    try:
        row = con.execute(
            "SELECT max(ts) FROM raw_signals WHERE signal_type = 'crypto_news'"
        ).fetchone()
    finally:
        con.close()
    if row and row[0]:
        ts = row[0]
        return ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)
    return None


def _stored_article_ids() -> set[str]:
    con = get_connection()
    try:
        rows = con.execute(
            "SELECT DISTINCT json_extract_string(payload, '$.articleId') "
            "FROM raw_signals WHERE signal_type = 'crypto_news'"
        ).fetchall()
    finally:
        con.close()
    return {r[0] for r in rows if r[0]}


def probe(q: str = "bitcoin", test_from: str = "2022-01-01", test_to: str = "2022-02-01") -> dict:
    """Spend ONE call to learn: (1) the key works, (2) whether history reaches
    ``test_from`` (the plan's lookback), (3) the real response/article shape.

    Queries a narrow old window; if it returns articles, this plan can reach that
    far back (backfill is viable). Returns a diagnostics dict.
    """
    data = search_all(q=q, frm=test_from, to=test_to, size=3, sort_by="date")
    arts = _articles(data)
    sample = arts[0] if arts else {}
    return {
        "ok": True,
        "top_level_keys": sorted(data.keys()),
        "num_results_field": next(
            (data.get(k) for k in ("numResults", "total", "count") if k in data), None
        ),
        "articles_returned": len(arts),
        "window": f"{test_from}..{test_to}",
        "reaches_window": len(arts) > 0,
        "sample_pub_date": _pub_date(sample),
        "sample_article_keys": sorted(sample.keys()) if sample else [],
        "sample_has_sentiment": "sentiment" in sample,
        "sample_title": (sample.get("title") or "")[:100],
    }


def print_probe(diag: dict) -> None:
    print("\n=== Perigon probe (1 API call spent) ===")
    print(f"  key works               : {diag.get('ok')}")
    print(f"  test window             : {diag.get('window')}")
    print(f"  history reaches window  : {diag.get('reaches_window')}  "
          f"(articles returned: {diag.get('articles_returned')})")
    print(f"  total results field     : {diag.get('num_results_field')}")
    print(f"  sample article pub date : {diag.get('sample_pub_date')}")
    print(f"  sample title            : {diag.get('sample_title')}")
    print(f"  article has 'sentiment' : {diag.get('sample_has_sentiment')}")
    print(f"  top-level response keys : {', '.join(diag.get('top_level_keys') or [])}")
    print(f"  article field keys      : {', '.join(diag.get('sample_article_keys') or [])}")
    if diag.get("reaches_window"):
        print("\n  -> history reaches 2022 on this plan: BACKFILL of a news/sentiment")
        print("     series is viable. See research/perigon-plan.md for the call budget.")
    else:
        print("\n  -> no 2022 articles: this plan's history is likely shallow (recent only).")
        print("     Best use is a FORWARD-accumulated monthly sentiment series, not backfill.")
