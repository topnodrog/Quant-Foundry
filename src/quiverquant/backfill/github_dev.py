"""Historical GitHub dev-activity backfill.

The live ``github`` collector only snapshots current stars/forks/issues per repo
— no history. This pulls each repo's full weekly commit history from
``/repos/{owner}/{repo}/stats/contributors`` (keyless works at 60 req/hr; set
GITHUB_TOKEN for 5000/hr) and stores it as ``dev_activity_history`` rows in
``raw_signals``, one per repo-week, deduped by (repo, week).

GitHub computes contributor stats asynchronously and answers 202 while a repo's
cache warms, so the fetch retries on 202. Weekly buckets are the aggregate of
commits/additions/deletions across the (up to ~500) returned contributors.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any

import requests

from quiverquant.collectors.dev_activity import DEFAULT_REPOS
from quiverquant.config import get_source
from quiverquant.storage import get_connection, insert_signals

GITHUB_API = "https://api.github.com"
SIGNAL_TYPE = "dev_activity_history"


def _headers() -> dict[str, str]:
    token = get_source("github").active_key()
    return {"Authorization": f"Bearer {token}"} if token else {}


def fetch_weekly_commits(
    repo: str,
    headers: dict[str, str] | None = None,
    max_retries: int = 6,
    sleep_s: float = 3.0,
) -> dict[int, dict[str, int]]:
    """Return ``{week_unix: {commits, additions, deletions}}`` for a repo.

    Aggregates GitHub's per-contributor weekly arrays. Retries on 202 (stats
    still computing); returns ``{}`` on persistent non-200.
    """
    url = f"{GITHUB_API}/repos/{repo}/stats/contributors"
    resp = None
    for _ in range(max_retries):
        resp = requests.get(url, headers=headers or {}, timeout=30)
        if resp.status_code == 202:  # computing — back off and retry
            time.sleep(sleep_s)
            continue
        break
    if resp is None or resp.status_code != 200:
        return {}

    weekly: dict[int, dict[str, int]] = {}
    for contributor in resp.json():
        for w in contributor.get("weeks", []):
            week = w.get("w")
            if week is None:
                continue
            bucket = weekly.setdefault(week, {"commits": 0, "additions": 0, "deletions": 0})
            bucket["commits"] += w.get("c", 0)
            bucket["additions"] += w.get("a", 0)
            bucket["deletions"] += w.get("d", 0)
    return weekly


def _seen_weeks(repo: str) -> set[str]:
    con = get_connection()
    try:
        rows = con.execute(
            "SELECT DISTINCT CAST(ts AS DATE) FROM raw_signals "
            "WHERE signal_type = ? AND entity = ?",
            [SIGNAL_TYPE, repo],
        ).fetchall()
    finally:
        con.close()
    return {r[0].isoformat() for r in rows if r[0]}


def weekly_to_records(
    repo: str,
    weekly: dict[int, dict[str, int]],
    seen_weeks: set[str],
    since: datetime | None = None,
) -> list[dict[str, Any]]:
    """Pure map: aggregated weekly commit buckets -> raw_signals records.

    Skips weeks before ``since`` and weeks already stored. Keeps zero-commit
    weeks — a lull in development is itself signal.
    """
    seen = set(seen_weeks)
    records: list[dict[str, Any]] = []
    for week in sorted(weekly):
        ts = datetime.fromtimestamp(int(week), tz=timezone.utc)
        if since is not None and ts < since:
            continue
        day = ts.date().isoformat()
        if day in seen:
            continue
        seen.add(day)
        bucket = weekly[week]
        records.append(
            {
                "source": "github",
                "signal_type": SIGNAL_TYPE,
                "entity": repo,
                "ts": ts,
                "tier": "free",
                "payload": {
                    "repo": repo,
                    "commits": int(bucket["commits"]),
                    "additions": int(bucket["additions"]),
                    "deletions": int(bucket["deletions"]),
                    "week": day,
                },
            }
        )
    return records


def backfill_dev_activity(
    repos: list[str] | None = None,
    since: datetime | None = None,
) -> int:
    """Backfill weekly commit history for ``repos`` (default watchlist). Returns
    rows added."""
    repos = repos or DEFAULT_REPOS
    headers = _headers()
    total = 0
    for repo in repos:
        weekly = fetch_weekly_commits(repo, headers)
        records = weekly_to_records(repo, weekly, _seen_weeks(repo), since)
        added = insert_signals(records)
        total += added
        print(f"[dev-activity] {repo}: +{added} weeks ({len(weekly)} available)")
    return total
