"""Tests for the derived graph VC features (pure logic, no DB).

Runs under pytest, or standalone: ``python tests/test_graph_features.py``.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from quiverquant.features.graph import (  # noqa: E402
    Backing,
    company_backers,
    compute_summary,
    conviction_ranking,
    fund_overlap,
    fund_portfolios,
)


def _b(fund: str, company: str) -> Backing:
    return Backing(fund=fund, company=company)


# a16z + Paradigm both back Uniswap and Aztec; a16z alone backs Solana.
SAMPLE = [
    _b("a16z", "Uniswap"),
    _b("a16z", "Aztec"),
    _b("a16z", "Solana"),
    _b("Paradigm", "Uniswap"),
    _b("Paradigm", "Aztec"),
    _b("Paradigm", "Blur"),
]


def test_company_backers_counts_distinct_funds():
    backers = company_backers(SAMPLE)
    assert backers["Uniswap"] == {"a16z", "Paradigm"}
    assert backers["Solana"] == {"a16z"}


def test_fund_portfolios():
    p = fund_portfolios(SAMPLE)
    assert p["a16z"] == {"Uniswap", "Aztec", "Solana"}
    assert p["Paradigm"] == {"Uniswap", "Aztec", "Blur"}


def test_conviction_ranking_only_multi_backed_sorted():
    conv = conviction_ranking(SAMPLE, min_funds=2)
    # Uniswap and Aztec have 2 backers; Solana/Blur have 1 (excluded).
    assert [c for c, _ in conv] == ["Aztec", "Uniswap"]  # tie on count -> alpha
    assert all(len(fs) == 2 for _, fs in conv)


def test_conviction_dedupes_repeated_edges():
    # a duplicate (fund, company) must not inflate the backer count
    dup = SAMPLE + [_b("a16z", "Uniswap")]
    assert company_backers(dup)["Uniswap"] == {"a16z", "Paradigm"}


def test_fund_overlap_shared_companies():
    ov = fund_overlap(SAMPLE)
    assert len(ov) == 1
    a, b, shared = ov[0]
    assert {a, b} == {"a16z", "Paradigm"}
    assert shared == ["Aztec", "Uniswap"]


def test_compute_summary_counts():
    s = compute_summary(SAMPLE, min_funds=2)
    assert s.n_backings == 6
    assert s.n_funds == 2
    assert s.n_companies == 4  # Uniswap, Aztec, Solana, Blur
    assert s.top_funds[0][1] == 3  # both funds back 3 each; sorted alpha -> a16z first
    assert len(s.conviction) == 2


def _run_standalone() -> int:
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    for fn in fns:
        try:
            fn()
            print(f"PASS {fn.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"FAIL {fn.__name__}: {e}")
    print(f"\n{len(fns) - failed}/{len(fns)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(_run_standalone())
