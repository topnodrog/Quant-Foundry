"""Pure mapping: one `raw_signals` row -> the governed-action calls that
reproduce it in the Open Foundry crypto ontology.

No network, no DB — every function here is deterministic and unit-testable, so
the whole translation can be validated with `migrate --dry-run` against the real
DuckDB before the stack is even up. Field mappings were derived from the actual
collector payloads (see ontology/crypto-pack/README.md).

Each row yields:
  * zero or more `Register*` calls (entities) carrying a `dedupe_key` so the
    migrator issues each entity once per run;
  * exactly one `Record*` call (the signal), with `dedupe_key=None`.
Unmappable rows (ticker_error, whale_alert_news) yield nothing.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable


@dataclass(frozen=True)
class ActionCall:
    action: str
    params: dict[str, Any] = field(default_factory=dict)
    #: natural key for Register* dedupe within a run; None means "always emit".
    dedupe_key: str | None = None


# ─── helpers ──────────────────────────────────────────────────────────────

def _iso(ts: Any) -> str | None:
    """Serialize a stored timestamp to an ISO-8601 UTC string with a Z suffix.
    Storage keeps naive-UTC wall-clock (see storage.py), so a naive value is
    treated as UTC."""
    if ts is None:
        return None
    if isinstance(ts, str):
        return ts
    if isinstance(ts, datetime):
        if ts.tzinfo is not None:
            ts = ts.astimezone(timezone.utc).replace(tzinfo=None)
        return ts.isoformat() + "Z"
    return str(ts)


def _date_to_dt(value: str | None) -> str | None:
    """`YYYY-MM-DD` (SEC file_date) -> `YYYY-MM-DDT00:00:00Z`; pass through
    anything already time-bearing."""
    if not value:
        return None
    if len(value) == 10 and value[4] == "-":
        return value + "T00:00:00Z"
    return value


def _chain_key(name: str | None) -> str | None:
    """Normalize a human chain name to a slug key: "Multi-Chain" -> "multi-chain"."""
    if not name:
        return None
    return re.sub(r"\s+", "-", name.strip().lower())


def _slugify(name: str | None) -> str | None:
    """Human project name -> a Protocol.slug natural key. Aligns with DefiLlama's
    lowercase-hyphenated slug style so a VC-backed "Uniswap" unifies onto the same
    Protocol node DefiLlama registers as "uniswap". Imperfect (won't merge
    "Uniswap Labs" vs "uniswap"), which is the expected first-cut of PLAN.md §4's
    hard entity-resolution problem."""
    if not name:
        return None
    slug = re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-")
    return slug or None


# EVM chain-id -> canonical Chain.key (extend as more chains are collected).
_EVM_CHAIN_KEYS = {"1": "ethereum"}


def _evm_chain_key(chain_id: str | None) -> str:
    if not chain_id:
        return "unknown"
    return _EVM_CHAIN_KEYS.get(str(chain_id), f"evm-{chain_id}")


_FROM_TO_RE = re.compile(r"from (.+?) to (.+?)\s*$", re.I)


def _parse_from_to(description: str | None) -> tuple[str | None, str | None]:
    """"transferred from unknown wallet to Galaxy Digital" -> (from, to) labels."""
    if not description:
        return None, None
    m = _FROM_TO_RE.search(description)
    if not m:
        return None, None
    return m.group(1).strip() or None, m.group(2).strip() or None


def _tier(row: dict[str, Any]) -> str:
    return "PAID" if str(row.get("tier", "free")).lower() == "paid" else "FREE"


# ─── per-signal handlers ──────────────────────────────────────────────────
# Each takes the full row and returns list[ActionCall].

def _h_ticker_snapshot(row):
    pl, ts, tier, src = row["payload"], _iso(row["ts"]), _tier(row), row["source"]
    ex = pl.get("exchange")
    pair = pl.get("symbol")
    base = pair.split("/")[0] if pair else None
    calls: list[ActionCall] = []
    if ex:
        calls.append(ActionCall("RegisterExchange",
                                {"exchangeKey": ex, "name": ex.capitalize(), "kind": "CEX"},
                                f"Exchange:{ex}"))
    if base:
        calls.append(ActionCall("RegisterToken", {"symbol": base}, f"Token:{base}"))
    calls.append(ActionCall("RecordPriceObservation", {
        "exchangeKey": ex, "pair": pair, "baseSymbol": base,
        "last": pl.get("last"), "bid": pl.get("bid"), "ask": pl.get("ask"),
        "baseVolume": pl.get("baseVolume"), "quoteVolume": pl.get("quoteVolume"),
        "observedAt": ts, "tier": tier, "source": src,
    }))
    return calls


def _h_tvl_snapshot(row):
    pl, ts, tier, src = row["payload"], _iso(row["ts"]), _tier(row), row["source"]
    slug = row["entity"]
    chain = pl.get("chain")
    chain_key = _chain_key(chain)
    calls: list[ActionCall] = []
    if chain_key:
        calls.append(ActionCall("RegisterChain", {"key": chain_key, "name": chain},
                                f"Chain:{chain_key}"))
    calls.append(ActionCall("RegisterProtocol", {
        "slug": slug, "name": pl.get("name") or slug,
        "category": pl.get("category"), "chainKey": chain_key,
    }, f"Protocol:{slug}"))
    tvl = pl.get("tvl")
    if tvl is not None:
        calls.append(ActionCall("RecordTvlObservation", {
            "protocolSlug": slug, "tvlUsd": tvl,
            "change1d": pl.get("change_1d"), "change7d": pl.get("change_7d"),
            "observedAt": ts, "tier": tier, "source": src,
        }))
    return calls


def _h_token_unlock_schedule(row):
    # Paid-tier DefiLlama path; shape unverified (no free key). Register the token
    # and record an unlock only when a date field can be found.
    pl, ts, tier, src = row["payload"], _iso(row["ts"]), _tier(row), row["source"]
    gecko = row["entity"]
    calls = [ActionCall("RegisterToken",
                        {"symbol": pl.get("symbol"), "geckoId": gecko},
                        f"Token:gecko:{gecko}")]
    unlock_at = None
    for k in ("nextEvent", "next_unlock", "date", "timestamp", "unlockDate"):
        if pl.get(k):
            unlock_at = _iso(pl[k]) if not isinstance(pl[k], str) else pl[k]
            break
    if unlock_at:
        calls.append(ActionCall("RecordUnlockEvent", {
            "tokenGeckoId": gecko, "unlockAt": unlock_at,
            "amountTokens": pl.get("amount"), "amountUsd": pl.get("amountUsd"),
            "pctOfCirculating": pl.get("pctOfCirculating"),
            "category": pl.get("category"),
            "observedAt": ts, "tier": tier, "source": src,
        }))
    return calls


def _h_whale_transfer(row):
    pl, ts, tier, src = row["payload"], _iso(row["ts"]), _tier(row), row["source"]
    token = row["entity"]
    from_label, to_label = _parse_from_to(pl.get("description"))
    calls = [ActionCall("RegisterToken", {"symbol": token}, f"Token:{token}")]
    calls.append(ActionCall("RecordWhaleTransfer", {
        "txHash": None, "tokenSymbol": token, "chainKey": None,
        "amountTokens": pl.get("amount"), "amountUsd": pl.get("usd_value"),
        "fromAddress": None, "toAddress": None,
        "fromLabel": from_label, "toLabel": to_label,
        "observedAt": ts, "tier": tier, "source": src,
    }))
    return calls


def _h_dune_query_row(row):
    # Default Dune query 7872020 = "eth whale transfers >500 ETH": every row is an
    # ETH transfer with structured from/to/hash. If other queries are wired in
    # later, branch on the row's columns here.
    pl, ts, tier, src = row["payload"], _iso(row["ts"]), _tier(row), row["source"]
    frm, to = pl.get("from_address"), pl.get("to_address")
    calls = [
        ActionCall("RegisterChain", {"key": "ethereum", "name": "Ethereum", "chainId": 1},
                   "Chain:ethereum"),
        ActionCall("RegisterToken", {"symbol": "ETH", "chainKey": "ethereum"}, "Token:ETH"),
    ]
    for addr in (frm, to):
        if addr:
            calls.append(ActionCall("RegisterWallet", {
                "address": addr, "chainKey": "ethereum",
                "category": "WHALE", "labelSource": "dune",
            }, f"Wallet:{addr}"))
    calls.append(ActionCall("RecordWhaleTransfer", {
        "txHash": pl.get("hash"), "tokenSymbol": "ETH", "chainKey": "ethereum",
        "amountTokens": pl.get("eth_value"), "amountUsd": None,
        "fromAddress": frm, "toAddress": to, "fromLabel": None, "toLabel": None,
        "observedAt": ts, "tier": tier, "source": src,
    }))
    return calls


_NANSEN_FUND = "Nansen Smart Money"


def _h_smart_money_holding(row):
    pl, ts, tier, src = row["payload"], _iso(row["ts"]), _tier(row), row["source"]
    sym, addr, chain = pl.get("token_symbol"), pl.get("token_address"), pl.get("chain")
    chain_key = _chain_key(chain)
    calls = [ActionCall("RegisterFund", {
        "name": _NANSEN_FUND, "kind": "SMART_MONEY",
        "description": "Nansen smart-money cohort",
    }, f"Fund:{_NANSEN_FUND}")]
    if sym:  # Token.symbol is required; only register when we have one
        calls.append(ActionCall("RegisterToken", {
            "symbol": sym, "contractAddress": addr, "chainKey": chain_key,
        }, f"Token:{sym}"))
    calls.append(ActionCall("RecordHolding", {
        "fundName": _NANSEN_FUND, "tokenSymbol": sym, "tokenAddress": addr,
        "chainKey": chain_key, "amountTokens": None, "amountUsd": pl.get("value_usd"),
        "observedAt": ts, "tier": tier, "source": src,
    }))
    return calls


def _h_chain_stats(row):
    pl, ts, tier, src = row["payload"], _iso(row["ts"]), _tier(row), row["source"]
    chain_key = row["entity"]  # blockchair uses lowercase slugs already
    return [
        ActionCall("RegisterChain", {"key": chain_key, "name": chain_key.capitalize()},
                   f"Chain:{chain_key}"),
        ActionCall("RecordChainMetric", {
            "chainKey": chain_key, "metricSet": "blockchair_stats", "data": pl,
            "observedAt": ts, "tier": tier, "source": src,
        }),
    ]


def _h_chain_supply(row):
    pl, ts, tier, src = row["payload"], _iso(row["ts"]), _tier(row), row["source"]
    chain_id = row["entity"]  # "1"
    chain_key = _evm_chain_key(chain_id)
    reg = {"key": chain_key, "name": chain_key.capitalize()}
    if str(chain_id).isdigit():
        reg["chainId"] = int(chain_id)
    return [
        ActionCall("RegisterChain", reg, f"Chain:{chain_key}"),
        ActionCall("RecordChainMetric", {
            "chainKey": chain_key, "metricSet": "etherscan_supply", "data": pl,
            "observedAt": ts, "tier": tier, "source": src,
        }),
    ]


def _h_repo_activity(row):
    pl, ts, tier, src = row["payload"], _iso(row["ts"]), _tier(row), row["source"]
    return [ActionCall("RecordDevActivity", {
        "repo": row["entity"], "stars": pl.get("stars"), "forks": pl.get("forks"),
        "openIssues": pl.get("open_issues"), "pushedAt": pl.get("pushed_at"),
        "observedAt": ts, "tier": tier, "source": src,
    })]


def _h_fulltext_filing_match(row):
    pl, ts, tier, src = row["payload"], _iso(row["ts"]), _tier(row), row["source"]
    names = pl.get("display_names") or []
    title = (names[0] if names else None) or pl.get("query") or "SEC filing"
    return [ActionCall("RecordRegulatoryFiling", {
        "kind": "FULLTEXT_MATCH", "title": title, "url": None,
        "ciks": row["entity"], "publishedAt": _date_to_dt(pl.get("file_date")),
        "observedAt": ts, "tier": tier, "source": src,
    })]


def _h_sec_rss(kind):
    def handler(row):
        pl, ts, tier, src = row["payload"], _iso(row["ts"]), _tier(row), row["source"]
        return [ActionCall("RecordRegulatoryFiling", {
            "kind": kind, "title": pl.get("title") or row["entity"] or "SEC filing",
            "url": pl.get("link"), "ciks": None, "publishedAt": ts,
            "observedAt": ts, "tier": tier, "source": src,
        })]
    return handler


def _h_fear_greed_index(row):
    pl, ts, tier, src = row["payload"], _iso(row["ts"]), _tier(row), row["source"]
    return [ActionCall("RecordSentiment", {
        "kind": "FEAR_GREED_INDEX", "tokenSymbol": None, "value": pl.get("value"),
        "classification": pl.get("classification"), "text": None, "url": None,
        "observedAt": ts, "tier": tier, "source": src,
    })]


def _h_sentiment_post(row):
    # CryptoPanic (dropped source; kept for completeness / historical rows).
    pl, ts, tier, src = row["payload"], _iso(row["ts"]), _tier(row), row["source"]
    currencies = [c.strip() for c in str(row.get("entity") or "").split(",") if c.strip()]
    return [ActionCall("RecordSentiment", {
        "kind": "NEWS_POST", "tokenSymbol": currencies[0] if currencies else None,
        "value": None, "classification": None,
        "text": pl.get("title") or pl.get("text"), "url": pl.get("url"),
        "observedAt": ts, "tier": tier, "source": src,
    })]


def _h_vc_portfolio_backing(row):
    # Firecrawl VC-portfolio rows (PLAN.md §3). The backing itself is the edge
    # (FundBacksProtocol carries round/announcedAt/sourceUrl), so this only
    # registers the two endpoint nodes; derive_edges builds the relationship.
    pl = row["payload"]
    fund = pl.get("fund_name")
    company = pl.get("company_name") or row["entity"]
    slug = _slugify(company)
    calls: list[ActionCall] = []
    if fund:
        calls.append(ActionCall("RegisterFund", {
            "name": fund, "kind": pl.get("fund_kind") or "VC",
            "description": pl.get("description"),
        }, f"Fund:{fund}"))
    if slug:
        calls.append(ActionCall("RegisterProtocol", {
            "slug": slug, "name": company, "category": pl.get("category"),
            "chainKey": None,
        }, f"Protocol:{slug}"))
    return calls


def _skip(row):
    return []


_HANDLERS: dict[str, Callable[[dict[str, Any]], list[ActionCall]]] = {
    "ticker_snapshot": _h_ticker_snapshot,
    "ticker_error": _skip,
    "tvl_snapshot": _h_tvl_snapshot,
    "token_unlock_schedule": _h_token_unlock_schedule,
    "whale_transfer": _h_whale_transfer,
    "whale_alert_news": _skip,
    "dune_query_row": _h_dune_query_row,
    "smart_money_holding": _h_smart_money_holding,
    "chain_stats": _h_chain_stats,
    "chain_supply": _h_chain_supply,
    "repo_activity": _h_repo_activity,
    "fulltext_filing_match": _h_fulltext_filing_match,
    "litigation_release": _h_sec_rss("LITIGATION_RELEASE"),
    "administrative_proceeding": _h_sec_rss("ADMIN_PROCEEDING"),
    "fear_greed_index": _h_fear_greed_index,
    "sentiment_post": _h_sentiment_post,
    "vc_portfolio_backing": _h_vc_portfolio_backing,
}


def map_row(row: dict[str, Any]) -> list[ActionCall]:
    """Translate one raw_signals row (source, signal_type, entity, ts, payload,
    tier) into ontology action calls. Unknown signal types map to nothing."""
    handler = _HANDLERS.get(row["signal_type"])
    if handler is None:
        return []
    return handler(row)


# ─── Graph edges ──────────────────────────────────────────────────────────
# Nodes are created first (map_row); edges are derived in a second pass because
# Open Foundry's createLink resolves endpoints by object ID, which only exists
# once the nodes are created. Each EdgeSpec names its endpoints by the SAME
# dedupe_key the Register* calls use, so the migrator can resolve them via the
# id index it built during the node pass.

@dataclass(frozen=True)
class EdgeSpec:
    action: str          # Link* action name
    from_key: str        # dedupe_key of the source node (matches a Register* call)
    to_key: str          # dedupe_key of the target node
    props: dict[str, Any] = field(default_factory=dict)


# action -> (from-endpoint param name, to-endpoint param name)
EDGE_ENDPOINT_PARAMS: dict[str, tuple[str, str]] = {
    "LinkWalletTransfer": ("fromWallet", "toWallet"),
    "LinkFundHolding": ("fund", "token"),
    "LinkTokenChain": ("token", "chain"),
    "LinkProtocolChain": ("protocol", "chain"),
    "LinkExchangeToken": ("exchange", "token"),
    "LinkFundBacksProtocol": ("fund", "protocol"),
}


def derive_edges(row: dict[str, Any]) -> list[EdgeSpec]:
    """Per-row edge contributions. The migrator aggregates these across rows
    (dedupes plain edges; sums/rolls up WalletTransferredTo and FundHoldsToken)
    before resolving endpoints and calling the Link* actions."""
    st, pl, ts = row["signal_type"], row["payload"], _iso(row["ts"])
    edges: list[EdgeSpec] = []

    if st == "dune_query_row":  # ETH whale transfers with structured from/to
        frm, to = pl.get("from_address"), pl.get("to_address")
        if frm and to:
            edges.append(EdgeSpec("LinkWalletTransfer", f"Wallet:{frm}", f"Wallet:{to}",
                                  {"lastTransferAt": ts, "amountUsd": None}))
        edges.append(EdgeSpec("LinkTokenChain", "Token:ETH", "Chain:ethereum"))

    elif st == "smart_money_holding":  # Nansen: fund holds token
        sym, chain = pl.get("token_symbol"), _chain_key(pl.get("chain"))
        if sym:
            edges.append(EdgeSpec("LinkFundHolding", f"Fund:{_NANSEN_FUND}", f"Token:{sym}",
                                  {"amountUsd": pl.get("value_usd"), "observedAt": ts}))
            if chain:
                edges.append(EdgeSpec("LinkTokenChain", f"Token:{sym}", f"Chain:{chain}"))

    elif st == "tvl_snapshot":  # protocol on chain
        chain = _chain_key(pl.get("chain"))
        if chain:
            edges.append(EdgeSpec("LinkProtocolChain", f"Protocol:{row['entity']}", f"Chain:{chain}"))

    elif st == "ticker_snapshot":  # exchange lists token
        ex, pair = pl.get("exchange"), pl.get("symbol")
        base = pair.split("/")[0] if pair else None
        if ex and base:
            edges.append(EdgeSpec("LinkExchangeToken", f"Exchange:{ex}", f"Token:{base}"))

    elif st == "vc_portfolio_backing":  # fund backs protocol
        fund, slug = pl.get("fund_name"), _slugify(pl.get("company_name") or row.get("entity"))
        if fund and slug:
            edges.append(EdgeSpec("LinkFundBacksProtocol", f"Fund:{fund}", f"Protocol:{slug}",
                                  {"round": pl.get("round"), "announcedAt": ts,
                                   "sourceUrl": pl.get("source_url")}))

    return edges


def aggregate_edges(specs: list[EdgeSpec]) -> list[EdgeSpec]:
    """Collapse per-row EdgeSpecs to one per (action, from, to). WalletTransferredTo
    rolls up transferCount/totalUsd/lastTransferAt; FundHoldsToken keeps the latest
    observation; the plain grouping edges just dedupe."""
    groups: dict[tuple[str, str, str], list[EdgeSpec]] = {}
    for s in specs:
        groups.setdefault((s.action, s.from_key, s.to_key), []).append(s)

    out: list[EdgeSpec] = []
    for (action, fk, tk), members in groups.items():
        if action == "LinkWalletTransfer":
            usd = [m.props.get("amountUsd") for m in members if m.props.get("amountUsd") is not None]
            props = {
                "transferCount": len(members),
                "totalUsd": sum(usd) if usd else None,
                "lastTransferAt": max(m.props["lastTransferAt"] for m in members),
            }
        elif action == "LinkFundHolding":
            latest = max(members, key=lambda m: m.props.get("observedAt") or "")
            props = {"amountUsd": latest.props.get("amountUsd"),
                     "observedAt": latest.props.get("observedAt")}
        elif action == "LinkFundBacksProtocol":
            latest = max(members, key=lambda m: m.props.get("announcedAt") or "")
            props = {"round": latest.props.get("round"),
                     "announcedAt": latest.props.get("announcedAt"),
                     "sourceUrl": latest.props.get("sourceUrl")}
        else:
            props = {}
        out.append(EdgeSpec(action, fk, tk, props))
    return out
