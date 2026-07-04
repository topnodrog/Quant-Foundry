# api.quiverquant.com (crypto alpha engine — research project)

**Status: Phase 1 complete (8 live collectors). Phase 2 (UNIFY layer) core is
live — the Open Foundry crypto Domain Pack loads on the running stack (Postgres
17 + Apache AGE; full ODL semantic validation passed) and the migration bridge
has ingested all 230 stored `raw_signals` rows into the ontology as 332
governed-action calls with 0 failures (verified 332 objects across all 15
types via REST). Remaining Phase 2 tails: populate the graph link edges
(node/observation objects are in; `WalletTransferredTo`/`FundHoldsToken`/etc.
edges are not yet) and add Firecrawl-sourced VC/unlock data. No backtesting,
paper trading, or execution code yet — see `PLAN.md` for the full roadmap.**

## Goal

Build a free/open-data clone of QuiverQuant's "alternative data" model, scoped to
crypto markets, by combining:

1. **Data collection** — replicate QuiverQuant-style alternative-data signals
   (insider/whale activity, sentiment, fund flows, dev activity) using free,
   publicly available crypto data sources instead of paid feeds.
2. **Scraping** — [Firecrawl.dev](https://firecrawl.dev) free tier (1,000
   pages/month) for sources without APIs.
3. **Strategy/execution engine** —
   [`nautechsystems/nautilus_trader`](https://github.com/nautechsystems/nautilus_trader)
   (confirmed primary engine), backtest → paper trade only for now, no live
   capital.
4. **Data unification** — `syzygyhack/open-foundry`, Phase 2 scope.

## Objective

Filter signal from noise across these sources and converge on a crypto
investment strategy that can be backtested and continuously re-qualified.
No strategy is "sure fire" — the aim is a rigorously validated, risk-managed
edge, not a guarantee.

## Layout

- `research/` — deep-dive notes per component, crypto-only scope
- `PLAN.md` — master plan tying everything together (source of truth for architecture)
- `src/quiverquant/` — implementation
  - `config.py` — per-source free/paid tier resolution from env vars
  - `storage.py` — DuckDB-backed append-only `raw_signals` table
  - `collectors/` — one module per PLAN.md §2 source
  - `ontology/` — Phase 2 bridge: maps `raw_signals` rows into the Open Foundry
    crypto ontology (`mapping.py` pure/tested, `client.py`, `migrate.py`)
- `ontology/crypto-pack/` — Open Foundry external Domain Pack (the UNIFY layer)
- `deploy/` — how to stand up Open Foundry with the crypto pack mounted
- `.env.example` — every API key a collector can use, and which sources need none
- `data/` — local DuckDB file, gitignored

## Running collectors

```
uv sync
uv run quiverquant                       # run all 8 collectors
uv run quiverquant defillama ccxt        # run specific ones
uv run quiverquant migrate-ontology --dry-run   # Phase 2: preview ontology ingestion
```

## Collector status (2026-07-03)

| # | Source | Module | Status |
|---|---|---|---|
| 1 | DefiLlama | `defillama.py` | TVL free & live; unlocks need `DEFILLAMA_API_KEY` (paid plan — PLAN.md assumed free, corrected) |
| 2 | CCXT | `ccxt_collector.py` | Live, no key |
| 3 | Etherscan V2 + Blockchair | `onchain.py` | Both live — Blockchair keyless, Etherscan confirmed against real key |
| 4 | CryptoPanic | `cryptopanic.py` | Needs `CRYPTOPANIC_API_KEY` (untested, no keyless tier) |
| 5 | Electric Capital + GitHub | `dev_activity.py` | GitHub half live, keyless; Electric Capital ecosystem mapping deferred (needs running their local export toolkit, not an API) |
| 6 | SEC EDGAR | `sec_edgar.py` | Live, no key |
| 7 | Whale Alert | `whale_alert.py` | Live — scrapes Telegram's public `t.me/s/whale_alert_io` preview page (Bot API can't read a channel we don't administer), deduped against stored post IDs |
| 8a | Nansen | `smart_money.py` | Live — smart-money holdings by chain, confirmed against a real key |
| 8b | Dune | `smart_money.py` | Live — query 7872020 (eth whale transfers >500 ETH, 3d window), created via Dune's Create Query API and wired as the default |

## Phase plan

- **Phase 0 (done):** gather components, research each, produce `PLAN.md`
- **Phase 1 (done):** data collectors above
- **Phase 2 (core done):** Open Foundry crypto Domain Pack (`ontology/crypto-pack/`)
  loads on the live stack (`deploy/`) and the migration bridge
  (`src/quiverquant/ontology/`) has ingested all 230 rows → 332 objects, verified.
  Tails: populate graph link edges, then Firecrawl-sourced VC/unlock data
- **Phase 3:** nautilus_trader integration, backtest first strategy
- **Phase 4:** walk-forward validation, statistical significance, paper trading
- **Phase 5 (not started, gated):** live capital — explicit separate go-ahead required
