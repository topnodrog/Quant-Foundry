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

from typing import Any

import requests

from quiverquant.config import get_source

_BASE = "https://api.perigon.io/v1"


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
    resp.raise_for_status()
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
