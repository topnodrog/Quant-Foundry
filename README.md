# api.quiverquant.com (crypto alpha engine — research project)

**Status: Phase 1 in progress. 6 of 8 data collectors live and tested against
real APIs; 2 need free/paid API keys the user hasn't supplied yet. No
backtesting, paper trading, or execution code yet — see `PLAN.md` for the
full phased roadmap.**

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
- `.env.example` — every API key a collector can use, and which sources need none
- `data/` — local DuckDB file, gitignored

## Running collectors

```
uv sync
uv run quiverquant                 # run all 8
uv run quiverquant defillama ccxt  # run specific ones
```

## Collector status (2026-07-02)

| # | Source | Module | Status |
|---|---|---|---|
| 1 | DefiLlama | `defillama.py` | TVL free & live; unlocks need `DEFILLAMA_API_KEY` (paid plan — PLAN.md assumed free, corrected) |
| 2 | CCXT | `ccxt_collector.py` | Live, no key |
| 3 | Etherscan V2 + Blockchair | `onchain.py` | Blockchair live, no key; Etherscan needs `ETHERSCAN_API_KEY` (untested) |
| 4 | CryptoPanic | `cryptopanic.py` | Needs `CRYPTOPANIC_API_KEY` (untested, no keyless tier) |
| 5 | Electric Capital + GitHub | `dev_activity.py` | GitHub half live, keyless; Electric Capital ecosystem mapping deferred (needs running their local export toolkit, not an API) |
| 6 | SEC EDGAR | `sec_edgar.py` | Live, no key |
| 7 | Whale Alert | `whale_alert.py` | Not implemented — needs a decision on Telegram Bot API vs. other free feed |
| 8 | Nansen/Dune | `smart_money.py` | Needs `DUNE_API_KEY` + real query IDs (Nansen has no free API tier) |

## Phase plan

- **Phase 0 (done):** gather components, research each, produce `PLAN.md`
- **Phase 1 (in progress):** data collectors above
- **Phase 2:** Open Foundry ontology, migrate collectors to write into it
- **Phase 3:** nautilus_trader integration, backtest first strategy
- **Phase 4:** walk-forward validation, statistical significance, paper trading
- **Phase 5 (not started, gated):** live capital — explicit separate go-ahead required
