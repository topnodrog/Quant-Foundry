"""Regression tests for the raw_signals -> ontology action mapping.

Payloads mirror real collector output (sampled from the DuckDB store). Runs
under pytest, or standalone: `python tests/test_ontology_mapping.py`.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from quiverquant.ontology.mapping import (  # noqa: E402
    ActionCall,
    aggregate_edges,
    derive_edges,
    map_row,
)

TS = datetime(2026, 7, 3, 4, 7, 35, tzinfo=timezone.utc)


def _by_action(calls: list[ActionCall]) -> dict[str, ActionCall]:
    return {c.action: c for c in calls}


def test_ticker_snapshot_registers_exchange_token_and_price():
    row = {
        "source": "ccxt", "signal_type": "ticker_snapshot", "entity": "binance:BTC/USDT",
        "ts": TS, "tier": "free",
        "payload": {"exchange": "binance", "symbol": "BTC/USDT", "bid": 1.0,
                    "ask": 2.0, "last": 1.5, "baseVolume": 10.0, "quoteVolume": 15.0},
    }
    calls = _by_action(map_row(row))
    assert calls["RegisterExchange"].params["exchangeKey"] == "binance"
    assert calls["RegisterExchange"].params["kind"] == "CEX"
    assert calls["RegisterToken"].params["symbol"] == "BTC"
    price = calls["RecordPriceObservation"].params
    assert price["pair"] == "BTC/USDT" and price["baseSymbol"] == "BTC"
    assert price["tier"] == "FREE" and price["observedAt"].endswith("Z")


def test_whale_alert_parses_from_to_labels():
    row = {
        "source": "whale_alert", "signal_type": "whale_transfer", "entity": "BTC",
        "ts": TS, "tier": "free",
        "payload": {"post_id": 1, "amount": 1631.0, "token": "BTC", "usd_value": 1e8,
                    "description": "transferred from unknown wallet to Galaxy Digital"},
    }
    wt = _by_action(map_row(row))["RecordWhaleTransfer"].params
    assert wt["tokenSymbol"] == "BTC"
    assert wt["fromLabel"] == "unknown wallet"
    assert wt["toLabel"] == "Galaxy Digital"
    assert wt["amountUsd"] == 1e8


def test_dune_row_makes_wallet_edges_and_eth_transfer():
    row = {
        "source": "dune", "signal_type": "dune_query_row", "entity": "0xhash",
        "ts": TS, "tier": "free",
        "payload": {"block_time": "2026-07-03 04:07:35.000 UTC", "eth_value": 510,
                    "from_address": "0xaaa", "hash": "0xhash", "to_address": "0xbbb"},
    }
    calls = map_row(row)
    wallets = [c for c in calls if c.action == "RegisterWallet"]
    assert {w.params["address"] for w in wallets} == {"0xaaa", "0xbbb"}
    wt = _by_action(calls)["RecordWhaleTransfer"].params
    assert wt["tokenSymbol"] == "ETH" and wt["chainKey"] == "ethereum"
    assert wt["txHash"] == "0xhash" and wt["amountTokens"] == 510
    assert wt["fromAddress"] == "0xaaa" and wt["toAddress"] == "0xbbb"


def test_nansen_holding_registers_fund_and_token():
    row = {
        "source": "nansen", "signal_type": "smart_money_holding", "entity": "UNI",
        "ts": TS, "tier": "free",
        "payload": {"chain": "ethereum", "token_address": "0x1f98",
                    "token_symbol": "UNI", "value_usd": 130080382.27},
    }
    calls = _by_action(map_row(row))
    assert calls["RegisterFund"].params["kind"] == "SMART_MONEY"
    assert calls["RegisterToken"].params["contractAddress"] == "0x1f98"
    holding = calls["RecordHolding"].params
    assert holding["fundName"] == "Nansen Smart Money"
    assert holding["amountUsd"] == 130080382.27


def test_tvl_snapshot_skips_record_when_tvl_missing():
    row = {
        "source": "defillama", "signal_type": "tvl_snapshot", "entity": "aave",
        "ts": TS, "tier": "free",
        "payload": {"name": "Aave", "chain": "Ethereum", "category": "Lending", "tvl": None},
    }
    actions = {c.action for c in map_row(row)}
    assert "RegisterProtocol" in actions
    assert "RecordTvlObservation" not in actions  # tvlUsd is required, guard drops it


def test_sec_rss_kinds_and_fulltext():
    lit = {
        "source": "sec_edgar", "signal_type": "litigation_release", "entity": "X",
        "ts": TS, "tier": "free",
        "payload": {"title": "SEC v. X", "link": "https://sec.gov/lr-1"},
    }
    admin = {**lit, "signal_type": "administrative_proceeding"}
    ft = {
        "source": "sec_edgar", "signal_type": "fulltext_filing_match", "entity": "0001",
        "ts": TS, "tier": "free",
        "payload": {"query": "crypto asset", "display_names": ["Foo (CIK 0001)"],
                    "file_date": "2025-02-27", "adsh": "x"},
    }
    assert map_row(lit)[0].params["kind"] == "LITIGATION_RELEASE"
    assert map_row(admin)[0].params["kind"] == "ADMIN_PROCEEDING"
    ftp = map_row(ft)[0].params
    assert ftp["kind"] == "FULLTEXT_MATCH"
    assert ftp["title"] == "Foo (CIK 0001)"
    assert ftp["publishedAt"] == "2025-02-27T00:00:00Z"


def _vc_row(fund: str, company: str, **pl) -> dict:
    return {
        "source": "firecrawl", "signal_type": "vc_portfolio_backing",
        "entity": company, "ts": TS, "tier": "free",
        "payload": {"fund_name": fund, "fund_kind": "VC", "company_name": company,
                    "category": pl.get("category"), "source_url": pl.get("url"),
                    "round": pl.get("round")},
    }


def test_vc_backing_registers_fund_and_protocol():
    row = _vc_row("a16z crypto", "Uniswap Labs", category="DeFi",
                  url="https://a16zcrypto.com/portfolio/")
    calls = _by_action(map_row(row))
    assert calls["RegisterFund"].params["name"] == "a16z crypto"
    assert calls["RegisterFund"].params["kind"] == "VC"
    proto = calls["RegisterProtocol"].params
    assert proto["slug"] == "uniswap-labs"      # slugified natural key
    assert proto["name"] == "Uniswap Labs" and proto["category"] == "DeFi"


def test_vc_backing_derives_fund_backs_protocol_edge():
    row = _vc_row("Paradigm", "Uniswap", url="https://www.paradigm.xyz/portfolio")
    edges = aggregate_edges(derive_edges(row))
    assert len(edges) == 1
    e = edges[0]
    assert e.action == "LinkFundBacksProtocol"
    assert e.from_key == "Fund:Paradigm" and e.to_key == "Protocol:uniswap"
    assert e.props["sourceUrl"] == "https://www.paradigm.xyz/portfolio"
    assert e.props["announcedAt"].endswith("Z")


def test_vc_backing_slug_unifies_with_defillama():
    # A VC-backed "Uniswap" and DefiLlama's "uniswap" protocol resolve to the
    # same Protocol dedupe_key, so the migrator links onto one shared node.
    vc = map_row(_vc_row("Pantera Capital", "Uniswap"))
    vc_proto = _by_action(vc)["RegisterProtocol"]
    assert vc_proto.dedupe_key == "Protocol:uniswap"


def test_vc_backing_edges_dedupe_across_funds():
    # Two funds backing the same project -> two distinct edges; same fund listing
    # the project twice -> one edge.
    rows = [_vc_row("a16z crypto", "Uniswap"), _vc_row("Paradigm", "Uniswap"),
            _vc_row("a16z crypto", "Uniswap")]
    specs = [s for r in rows for s in derive_edges(r)]
    edges = aggregate_edges(specs)
    pairs = {(e.from_key, e.to_key) for e in edges}
    assert pairs == {("Fund:a16z crypto", "Protocol:uniswap"),
                     ("Fund:Paradigm", "Protocol:uniswap")}


def test_unmapped_types_yield_nothing():
    for st in ("whale_alert_news", "ticker_error"):
        row = {"source": "x", "signal_type": st, "entity": None, "ts": TS,
               "tier": "free", "payload": {}}
        assert map_row(row) == []


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
