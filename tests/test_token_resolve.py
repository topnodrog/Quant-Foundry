"""Tests for VC-name -> token resolution (pure matching logic, no network).

Runs under pytest, or standalone: ``python tests/test_token_resolve.py``.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from quiverquant.features.token_resolve import _norm, resolve  # noqa: E402

UNIVERSE = [
    {"id": "uniswap", "symbol": "uni", "name": "Uniswap", "market_cap_rank": 42},
    {"id": "optimism", "symbol": "op", "name": "Optimism", "market_cap_rank": 153},
    # two coins named "Compound" — the higher-mcap (first) one must win
    {"id": "compound-governance-token", "symbol": "comp", "name": "Compound", "market_cap_rank": 187},
    {"id": "compound-fake", "symbol": "cmpd", "name": "Compound", "market_cap_rank": 4000},
    {"id": "finance-scam", "symbol": "fin", "name": "Finance", "market_cap_rank": 900},
]


def test_norm_strips_and_lowercases():
    assert _norm("Magic Eden") == "magiceden"
    assert _norm("dYdX") == "dydx"
    assert _norm("a16z crypto") == "a16zcrypto"


def test_resolve_exact_name_match():
    got = resolve(["Uniswap", "Optimism"], UNIVERSE)
    assert {r.company for r in got} == {"Uniswap", "Optimism"}
    assert next(r for r in got if r.company == "Uniswap").symbol == "UNI"


def test_resolve_no_match_dropped():
    got = resolve(["Coinbase", "Uniswap"], UNIVERSE)  # Coinbase not in universe
    assert [r.company for r in got] == ["Uniswap"]


def test_resolve_denylist_category_headers():
    # "Finance" is an a16z category header that leaked into company_name
    got = resolve(["Finance", "Uniswap"], UNIVERSE)
    assert [r.company for r in got] == ["Uniswap"]


def test_resolve_first_wins_on_duplicate_name():
    got = resolve(["Compound"], UNIVERSE)
    assert len(got) == 1
    assert got[0].gecko_id == "compound-governance-token"  # higher-mcap, listed first


def test_resolve_sorted_by_rank():
    got = resolve(["Optimism", "Uniswap"], UNIVERSE)
    assert [r.company for r in got] == ["Uniswap", "Optimism"]  # 42 before 153


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
