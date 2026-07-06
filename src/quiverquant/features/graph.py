"""VC-conviction and fund co-investment features from the ontology's
``FundBacksProtocol`` edges (stored as ``vc_portfolio_backing`` rows).

Pure functions operate on ``(fund, company)`` pairs so they are unit-testable
without a database; ``read_backings`` is the DuckDB read side. This is lever #2
from ``research/open-foundry-strategic-advantage.md`` — a relationship signal
(who co-invests with whom, which projects have the most independent VC
conviction) that no single collector's flat rows expose.

Honest scope note: these features are **cross-sectional and point-in-time as of
the last VC-portfolio scrape** — they are not yet a backtestable time series, so
they do not feed the market-timing gates (`walkforward`/`significance`) that run
on BTC price. They become tradeable either (a) cross-sectionally, once we collect
per-project token OHLCV to rank a long book, or (b) temporally, once repeated
scrapes accumulate a history of *when* each backing appeared. Until then this is a
research/screening signal and the scaffolding for those next steps.
"""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass

from quiverquant.storage import get_connection

_SIGNAL_TYPE = "vc_portfolio_backing"


@dataclass(frozen=True)
class Backing:
    """One (fund → company) portfolio edge."""

    fund: str
    company: str
    fund_kind: str | None = None
    category: str | None = None


def read_backings() -> list[Backing]:
    """Load VC-portfolio backing edges from ``raw_signals``."""
    con = get_connection()
    try:
        rows = con.execute(
            "SELECT payload FROM raw_signals WHERE signal_type = ?", [_SIGNAL_TYPE]
        ).fetchall()
    finally:
        con.close()

    out: list[Backing] = []
    for (payload,) in rows:
        p = payload if isinstance(payload, dict) else json.loads(payload)
        fund = p.get("fund_name")
        company = p.get("company_name")
        if not fund or not company:
            continue
        out.append(
            Backing(
                fund=str(fund),
                company=str(company),
                fund_kind=p.get("fund_kind"),
                category=p.get("category"),
            )
        )
    return out


def _pairs(backings: list[Backing]) -> set[tuple[str, str]]:
    """Deduped (fund, company) pairs."""
    return {(b.fund, b.company) for b in backings}


def company_backers(backings: list[Backing]) -> dict[str, set[str]]:
    """company -> set of distinct funds backing it."""
    out: dict[str, set[str]] = defaultdict(set)
    for fund, company in _pairs(backings):
        out[company].add(fund)
    return dict(out)


def fund_portfolios(backings: list[Backing]) -> dict[str, set[str]]:
    """fund -> set of distinct companies it backs."""
    out: dict[str, set[str]] = defaultdict(set)
    for fund, company in _pairs(backings):
        out[fund].add(company)
    return dict(out)


def conviction_ranking(backings: list[Backing], min_funds: int = 2) -> list[tuple[str, list[str]]]:
    """Companies backed by ``>= min_funds`` distinct funds, most-backed first.

    "VC conviction" = independent-backer count. A project multiple top funds
    separately chose to back is a stronger prior than one on a single portfolio.
    """
    backers = company_backers(backings)
    multi = [(c, sorted(fs)) for c, fs in backers.items() if len(fs) >= min_funds]
    multi.sort(key=lambda cf: (-len(cf[1]), cf[0]))
    return multi


def fund_overlap(backings: list[Backing], min_shared: int = 1) -> list[tuple[str, str, list[str]]]:
    """Fund pairs and the companies they both back, most-overlapping first — the
    co-investment clustering structure. Returns ``(fundA, fundB, shared companies)``.
    """
    portfolios = fund_portfolios(backings)
    funds = sorted(portfolios)
    out: list[tuple[str, str, list[str]]] = []
    for i, a in enumerate(funds):
        for b in funds[i + 1:]:
            shared = sorted(portfolios[a] & portfolios[b])
            if len(shared) >= min_shared:
                out.append((a, b, shared))
    out.sort(key=lambda t: (-len(t[2]), t[0], t[1]))
    return out


@dataclass(frozen=True)
class GraphFeatureSummary:
    n_backings: int
    n_funds: int
    n_companies: int
    conviction: list[tuple[str, list[str]]]
    overlap: list[tuple[str, str, list[str]]]
    top_funds: list[tuple[str, int]]


def compute_summary(backings: list[Backing], min_funds: int = 2) -> GraphFeatureSummary:
    backers = company_backers(backings)
    portfolios = fund_portfolios(backings)
    top_funds = sorted(((f, len(cs)) for f, cs in portfolios.items()), key=lambda x: (-x[1], x[0]))
    return GraphFeatureSummary(
        n_backings=len(_pairs(backings)),
        n_funds=len(portfolios),
        n_companies=len(backers),
        conviction=conviction_ranking(backings, min_funds=min_funds),
        overlap=fund_overlap(backings, min_shared=1),
        top_funds=top_funds,
    )


def print_summary(s: GraphFeatureSummary, limit: int = 20) -> None:
    print("\n=== Graph-derived VC features (FundBacksProtocol edges) ===")
    print(f"  backings (edges): {s.n_backings}   funds: {s.n_funds}   companies: {s.n_companies}")

    print(f"\n  Top funds by portfolio size:")
    for fund, n in s.top_funds[:limit]:
        print(f"    {fund:24} {n}")

    print(f"\n  VC conviction - companies backed by >=2 distinct funds ({len(s.conviction)}):")
    if not s.conviction:
        print("    (none — current scrape has little fund overlap)")
    for company, funds in s.conviction[:limit]:
        print(f"    {company:24} {len(funds)}  {', '.join(funds)}")

    print(f"\n  Fund co-investment overlap (shared portfolio companies):")
    if not s.overlap:
        print("    (none)")
    for a, b, shared in s.overlap[:limit]:
        print(f"    {a} + {b}: {len(shared)}  ({', '.join(shared)})")
    print(
        "\n  Note: cross-sectional as of the last VC scrape - a screening signal,"
        "\n  not yet a backtestable time series (see module docstring)."
    )
