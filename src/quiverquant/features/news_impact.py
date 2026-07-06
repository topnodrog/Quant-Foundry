"""Did news move the market? Budget-aware event study over Perigon news.

Approach (associational, not causal — see caveat): take BTC's biggest single-day
moves from our cached price history, then spend ONE Perigon call per day to pull
that day's crypto news + sentiment. Tabulate move %, article volume, average
sentiment, and the top headline, so we can eyeball whether big moves have obvious
news catalysts and whether news sentiment lines up with the move's direction.

Call budget: one call per move-day examined (``--top N``) — keep N small; the plan
is 150 calls/month. Perigon history reaches ~2022, so days are restricted to that.

Honest caveat: news and price are roughly simultaneous, causality runs both ways
(a crash *generates* news), and this samples ≤100 articles/day. So this reveals
*association*, not proof that news caused the move.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from quiverquant.collectors.perigon import search_all, _articles

_CRYPTO_Q = "bitcoin OR ethereum OR crypto OR cryptocurrency"
_PERIGON_HISTORY_START = "2022-01-01"


@dataclass(frozen=True)
class DayImpact:
    date: str
    move_pct: float
    num_results: int | None
    articles_sampled: int
    net_sentiment: float | None  # avg(positive - negative) over sampled articles
    top_headline: str


def top_move_days(n: int = 10, since: str = _PERIGON_HISTORY_START) -> list[tuple[str, float]]:
    """Largest |daily return| BTC days on/after ``since``: [(YYYY-MM-DD, pct)]."""
    from quiverquant.backtest.ohlcv import read_ohlcv_df

    df = read_ohlcv_df("binance", "BTC/USDT", "1d")
    if df.empty:
        return []
    df = df[df.index >= f"{since}T00:00:00+00:00"]
    ret = df["close"].pct_change().dropna()
    top = ret.reindex(ret.abs().sort_values(ascending=False).index)[:n]
    return [(ts.strftime("%Y-%m-%d"), round(float(v) * 100, 2)) for ts, v in top.items()]


def _avg_net_sentiment(articles: list[dict]) -> float | None:
    tot, k = 0.0, 0
    for a in articles:
        s = a.get("sentiment")
        if isinstance(s, dict):
            tot += float(s.get("positive", 0) or 0) - float(s.get("negative", 0) or 0)
            k += 1
    return round(tot / k, 3) if k else None


def _top_headline(articles: list[dict]) -> str:
    if not articles:
        return ""
    best = max(articles, key=lambda a: float(a.get("score", 0) or 0))
    return (best.get("title") or "")[:90]


def news_for_day(date: str) -> dict:
    """One Perigon call: crypto articles published on ``date`` (UTC day)."""
    from datetime import date as _d

    y, m, d = (int(x) for x in date.split("-"))
    nxt = (_d(y, m, d) + timedelta(days=1)).isoformat()
    return search_all(q=_CRYPTO_Q, frm=date, to=nxt, size=100, sort_by="date")


def run_news_impact(n: int = 10) -> list[DayImpact]:
    """For each of BTC's top-``n`` move days, spend one call and summarise the news."""
    out: list[DayImpact] = []
    for date, move in top_move_days(n):
        data = news_for_day(date)
        arts = _articles(data)
        out.append(
            DayImpact(
                date=date,
                move_pct=move,
                num_results=next((data.get(k) for k in ("numResults", "total") if k in data), None),
                articles_sampled=len(arts),
                net_sentiment=_avg_net_sentiment(arts),
                top_headline=_top_headline(arts),
            )
        )
    return out


def print_impact(rows: list[DayImpact]) -> None:
    print("\n=== Did news move BTC? Top single-day moves vs that day's crypto news ===")
    print(f"  {'date':11} {'move%':>8} {'articles':>9} {'net_sent':>9}  top headline")
    aligned = 0
    for r in rows:
        ns = "n/a" if r.net_sentiment is None else f"{r.net_sentiment:+.2f}"
        vol = r.num_results if r.num_results is not None else r.articles_sampled
        print(f"  {r.date:11} {r.move_pct:>+8.2f} {vol:>9} {ns:>9}  {r.top_headline}")
        if r.net_sentiment is not None and (r.net_sentiment > 0) == (r.move_pct > 0):
            aligned += 1
    n = sum(1 for r in rows if r.net_sentiment is not None)
    if n:
        print(f"\n  sentiment sign matched move sign on {aligned}/{n} days "
              f"(50% = coin-flip; news sentiment is contemporaneous, not predictive)")
    print("  NOTE: associational only - a crash generates bearish news as much as the reverse.")
