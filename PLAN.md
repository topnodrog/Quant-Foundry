# Master Plan — Crypto Alt-Data & Strategy Engine

**Status (updated 2026-07-08): Phases 0-3 done, Phase 4 in progress — 6 candidates through the
gates, none qualify. The survivorship-free re-run of candidate 6 (§9 steps 1-2, DONE) is the
project's most decisive result: the same momentum config that returned +5,212% on today's-liquid
universe returns −44% on the point-in-time universe (417 coins incl. dead ones vs 48) — the entire
edge was survivorship bias. Walk-forward on the unbiased data found real ranking information at the
weekly cadence (3/4 folds beat the random null; one at p=0.005) but a long-only alt book still
compounds to −51% OOS. Next candidate: long-short / regime-gated momentum (§9). 9 collectors are live (§2,
incl. the Firecrawl VC-portfolio scraper §3); the Open Foundry crypto Domain Pack (§4) loads on the
running stack and `raw_signals` rows are ingested into the ontology, graph edges included (latest
live graph: 570 vertices / 327 edges). Phase 3 built the nautilus_trader backtest pipeline and a
first strategy (Fear & Greed contrarian). Phase 4 built the qualification harness (walk-forward +
permutation significance, §6 steps 2-3) and used it to judge that first strategy — which does NOT
qualify (fails both gates; see the Phase 4 entry in §9). No capital at risk — backtest/validation
only, no paper-trading or live execution yet. Phase 5 not started. `README.md` tracks live status.**
Synthesizes: `research/quiverquant-data-landscape.md`, `research/firecrawl.md`,
`research/github-openfoundry-nautilus.md`, `research/github-quanthedgefund-alphascanner.md`,
`research/liquid-trade-coinvest-ai.md`.

## 0. Reframing the goal

The brief was a "sure fire crypto investment strategy." There isn't one — anything marketed as
guaranteed is either lying or hasn't hit its bad month yet. What research actually supports
building is a **rigorously and continuously qualified** strategy: real free data, real backtests,
real out-of-sample validation, real paper trading, with explicit numeric gates before any dollar
is at risk, and ongoing re-qualification after that. Section 6 defines what "qualify" means
concretely — that's the mechanism that stands in for "sure fire."

---

## 1. Component verdicts

| Requested component | Verdict | Role |
|---|---|---|
| api.quiverquant.com (data) | Replace with ~30 free sources | Data layer (§2) |
| Firecrawl.dev | Confirmed, free tier viable | Scrape-only-what-has-no-API gap-filler (§3) |
| OpenFoundry | **Resolved** → [syzygyhack/open-foundry](https://github.com/syzygyhack/open-foundry) | Ontology/data-unification layer (§4) — not a trading tool, repurposed |
| nautechsystems/nautilus_trader | Confirmed strong fit | Primary backtest + execution engine (§5) |
| QuantHedgeFund | **No viable repo exists** under this name (unlicensed, thin crypto support, or hallucinated URLs) | Dropped — role absorbed by nautilus_trader / freqtrade |
| Crypto-Alpha-Scanner | **No viable repo exists** (real match is an n8n JSON file, not code) | Dropped — role absorbed by freqtrade's pairlist screening or CryptoSignal (fork required) |
| liquid.trade / coinvest.ai | Confirmed real, same company; usable but flagged | Candidate execution layer, **simulation-mode only until regulatory posture is independently verified** (§7) |

---

## 2. Data layer — what to actually collect

Full source-by-source detail in `research/quiverquant-data-landscape.md` (30 sources compared).
Build in this order — each tier is free, requires no scraping, and adds one QuiverQuant-style
signal category:

| Order | Source | Signal category | Effort |
|---|---|---|---|
| 1 | DefiLlama API | On-chain fundamentals, TVL/flows, token unlocks | Trivial |
| 2 | CCXT (100+ exchanges) | Cross-exchange order book/trade/volume | Trivial |
| 3 | Etherscan V2 + Blockchair | Wallet/tx base layer (all whale/insider signals build on this) | Trivial |
| 4 | CryptoPanic API | Sentiment (community-voted Panic Score) | Trivial |
| 5 | Electric Capital `crypto-ecosystems` + GitHub API | Dev activity ("patents" analog) | Light SDK |
| 6 | SEC EDGAR full-text search + Litigation RSS | Regulatory/enforcement ("lobbying" analog) | Trivial |
| 7 | Whale Alert (X/Telegram feed, not paid API) | Real-time large-tx alerts | Light scraping |
| 8 | Nansen (free credits) + Dune Analytics (2,500 credits/mo, API included) | Smart-money wallet labels, flexible on-chain SQL | Light SDK / Heavy |

**Explicitly not free / deprioritized:** Glassnode, CryptoQuant API, Whale Alert API, X/Twitter
API, LunarCrush official API, CoinGlass API — all paid-only. CryptoQuant's headline metrics are
reachable free via community Dune dashboards instead of the paid API. Flipside Crypto's free-data
future is unconfirmed (possible platform transition) — re-verify before use.

---

## 3. Firecrawl — spend the 1,000 pages/month only where no free API exists

Full detail in `research/firecrawl.md`. Rule: **check for a free API/RSS before spending a
credit.** SEC, CFTC, and most major crypto news outlets already have RSS — don't scrape those.

Recommended allocation (~1,000 credits/month, `/map` first to scope any new target):

| Category | Cadence | Est. credits |
|---|---|---|
| VC portfolio pages (a16z, Paradigm, Multicoin, Dragonfly, Pantera, Coinbase Ventures) — "who's backing what" | Bi-weekly | ~150 |
| Token unlock/vesting calendars (CryptoRank, CMC unlocks, per-project pages) | Weekly overview / monthly per-project | ~150 |
| Exchange listing announcements (Binance, Coinbase, Upbit, OKX) via `/monitor` | Daily | ~150 |
| Non-RSS regulatory pages (state/foreign, verified individually) | Weekly | ~50 |
| Project docs/whitepaper ingestion, `/map` then selective `/crawl` | Monthly, event-driven | ~250-300 |
| Buffer for ad hoc `/search` | As needed | ~200-250 |

Gotchas to build defensively around: `/crawl` defaults to a 10,000-page limit (always pass an
explicit low `limit`), credits don't roll over, job output expires after 24h (persist
immediately), enhanced/stealth proxy costs 5x — default to `basic`/`auto`.

---

## 4. Data-unification layer — Open Foundry

`syzygyhack/open-foundry` (Apache-2.0, TypeScript/Go, Postgres+Apache AGE) has zero built-in
crypto logic but is a real fit for the hardest non-trading problem here: unifying ~10 disparate
free sources — each with its own schema, refresh cadence, and identifier scheme (wallet address vs
ticker vs protocol slug) — into one queryable ontology before any strategy engine touches it.

Plan: build a custom **crypto Domain Pack** modeling entities (Wallet, Protocol, Token, VC/Fund,
Exchange, UnlockEvent) and relationships (Wallet→holds→Token, VC→backs→Protocol,
Wallet→transferred_to→Wallet). Use its CEL action framework for cross-source triggers (e.g. "a
wallet tagged as a known VC moved >$1M to a CEX deposit address" → emit an event). Its existing AML
domain pack is a usable reference pattern for the regulatory/compliance category.

This is genuinely more engineering effort than any single data collector — treat it as Phase 2,
not Phase 1. Phase 1 can run on a plain Postgres/DuckDB schema; migrate to Open Foundry once the
collector set stabilizes and the entity-relationship model is clear enough to encode properly.

---

## 5. Strategy / backtest / execution engine — nautilus_trader (primary)

Confirmed strong fit (full detail in `research/github-openfoundry-nautilus.md`):

- LGPL-3.0 — safe to use as an unmodified dependency without open-sourcing proprietary strategy
  code, as long as we extend via its API rather than fork-modifying internals.
- Crypto coverage: Binance, Coinbase, Bybit, OKX, Kraken, BitMEX, Deribit (CEX) + dYdX, Hyperliquid,
  Derive, Lighter (DEX) — stable adapters with historical+live data and execution reconciliation.
- Custom-data framework (`Data` subclass + `publish_data`/`subscribe_data`) is architecturally
  built for exactly this project's need: stream on-chain/sentiment/dev-activity signals into a
  strategy interleaved correctly with price data, avoiding lookahead bias.
- Research/live parity (same `Strategy` code runs in backtest and live) directly serves the
  "continuously re-qualify" goal — less backtest-to-live drift than most frameworks.
- Risk: pre-1.0 versioning, breaking changes between minor releases — pin versions.

**Secondary/fallback:** `freqtrade` (52k★, crypto-native, GPL-3.0, huge community, FreqAI ML
module) if nautilus_trader's learning curve proves too steep for a first working strategy —
faster to a working bot, narrower architecture. `jesse-ai/jesse` (MIT, simpler API) as a
lighter-weight third option.

**Regime-detection add-on:** [jackson-video-resources/markov-hedge-fund-method](https://github.com/jackson-video-resources/markov-hedge-fund-method)
(user-provided, not in original scope) — MIT-licensed (GitHub's license
detector misflags it as "Other" due to an added attribution clause, but the
LICENSE file is standard MIT text plus "credit encouraged," which is
non-binding), single ~20KB Python script (`scripts/markov_regime.py`) that
labels Bull/Bear/Sideways via a 3×3 transition matrix and forecasts n-steps
ahead via Chapman-Kolmogorov, plus a TradingView Pine Script indicator and a
Claude Code skill wrapper. Created/pushed in a one-day burst (2026-05-19/20)
with 316★/186 forks — a star count disproportionate to one day of commits is
usually a red flag (same pattern as the Crypto-Alpha-Scanner n8n repo), but
here the commit history shows genuine iteration (a bug fix credited to an
external contributor, "Yaniv Haver") and real, readable source rather than a
template — treat as legitimate, just young and single-author. Fits as a
lightweight **regime filter** feeding into nautilus_trader as a custom-data
signal: gate which strategies are active by regime (e.g. momentum in Bull,
mean-reversion in Sideways, reduced exposure in Bear) rather than as a
standalone strategy. Worth backtesting on crypto (BTC-USD is used as the
README's own example ticker) before trusting its regime calls.

**Scanner role (replaces Crypto-Alpha-Scanner):** freqtrade's pairlist/whitelist system run in
dry-run mode is a de facto multi-pair alpha scanner using a live, maintained codebase, instead of
reimplementing `xCodeWraith/Crypto-Alpha-Scanner`'s single n8n JSON file. `CryptoSignal/crypto-signal`
(MIT, purpose-built TA scanner, 500+ coins) is a closer conceptual match but stale since 2024 —
usable only if forked and dependency-updated first.

---

## 6. Strategy qualification framework (the "background work to qualify the strategy")

This is the mechanism that replaces "sure fire." Every candidate strategy moves through gates,
in order, and any failed gate sends it back for revision — none are skippable:

1. **Backtest** — nautilus_trader `BacktestEngine`/`BacktestNode` against historical data +
   alt-data signals from §2/§4. Realistic fill/slippage models (not just mid-price fills), fee
   modeling matched to actual venue fee tiers.
2. **Walk-forward validation** — rolling out-of-sample windows via `BacktestEngine.reset()` +
   scripted orchestration (not turnkey in nautilus_trader — build this ourselves). A strategy that
   only works on the exact historical window it was tuned on is overfit, not qualified.
3. **Statistical significance check** — compare realized Sharpe/Sortino/max-drawdown against a
   randomized/shuffled-signal baseline. If a strategy can't beat noise by a meaningful margin
   across multiple out-of-sample windows, it doesn't graduate.
4. **Paper trading** — live data, live signals, zero capital. nautilus_trader supports this
   natively against real exchange feeds; alternatively Co-Invest Computer's simulation/dry-run mode
   (§7) if using Liquid as the eventual execution venue.
5. **Gated live promotion** — minimum paper-trading duration (e.g. full market cycle exposure, not
   just a lucky week) and explicit numeric thresholds (max drawdown ceiling, minimum live Sharpe,
   minimum trade count for statistical power) agreed before any capital is committed — decided
   later, not defaulted silently.
6. **Continuous re-qualification** — once live, the strategy is re-run through steps 1-3 on a
   rolling basis; live performance that diverges from backtest expectation beyond a set tolerance
   triggers automatic de-risking, not manual discovery after the fact.

None of this is built yet — it's the Phase 3/4 scope once the data and engine layers exist.

---

## 7. Execution layer — liquid.trade / coinvest.ai, with real caveats

Full detail and sourcing in `research/liquid-trade-coinvest-ai.md`. Key facts: `coinvest.ai` is
not a separate company — it 301-redirects to Liquid's own "Co-Invest" product. **Co-Invest
Computer** (MCP-based automated trading) is the actually-relevant integration point: it has
built-in risk controls (max notional/leverage, mandatory stop-loss, symbol allowlists, daily order
caps) and a genuine simulation/dry-run mode, which lines up well with the Phase 4 paper-trading
gate above.

**But before routing anything through it:**
- Liquid's basis for not registering as a broker/exchange leans on a CFTC no-action letter
  (26-09) issued specifically to a different company (Phantom) under ten conditions Phantom
  agreed to — not a general exemption Liquid is legally covered by. This is a real, unresolved
  regulatory question, not a formality.
- No disclosed legal entity, jurisdiction, or license found anywhere public.
- Both the company (~1 year) and Co-Invest Computer specifically (~2 months) are very young, with
  no track record through a stressed market.
- Execution is non-custodial, routed through Hyperliquid/Lighter/Ostium — Liquid is a UX/aggregation
  layer on top of those venues, not the actual counterparty.

**Recommendation:** treat Co-Invest Computer as **simulation-mode only** for Phase 4 paper trading
— it's genuinely well-suited for that and costs nothing to try. Do not route real capital through
it without independently confirming (directly from Liquid, not marketing copy) their actual legal
entity, jurisdiction, and terms. In parallel, evaluate integrating directly with **Hyperliquid**
(mature, well-documented Python SDK, already a nautilus_trader-supported venue) as a lower-risk
execution path that skips the Liquid intermediary layer entirely for the live-capital stage, if it
ever gets there.

---

## 8. Architecture (textual)

```
 ┌─────────────────────────────────────────────────────────────┐
 │  COLLECT (§2)                                                │
 │  DefiLlama · CCXT · Etherscan/Blockchair · CryptoPanic ·     │
 │  Electric Capital + GitHub API · SEC/CFTC feeds ·            │
 │  Whale Alert feed · Nansen · Dune         + Firecrawl (§3)   │
 │  for VC pages / unlock calendars / listing pages / docs      │
 └───────────────────────────┬───────────────────────────────────┘
                              ▼
 ┌─────────────────────────────────────────────────────────────┐
 │  UNIFY — Open Foundry ontology (§4)                          │
 │  Wallet / Protocol / Token / VC / Exchange / UnlockEvent      │
 │  entities + relationships; CEL-triggered cross-source events  │
 │  (Phase 1: plain Postgres/DuckDB until this is built)         │
 └───────────────────────────┬───────────────────────────────────┘
                              ▼
 ┌─────────────────────────────────────────────────────────────┐
 │  STRATEGY / BACKTEST — nautilus_trader (§5)                  │
 │  custom-data signals + price data → Strategy → qualification │
 │  gates (§6): backtest → walk-forward → significance → paper  │
 └───────────────────────────┬───────────────────────────────────┘
                              ▼
 ┌─────────────────────────────────────────────────────────────┐
 │  EXECUTE (§7) — simulation-first                              │
 │  Co-Invest Computer (sim mode) or Hyperliquid direct SDK      │
 │  Real capital gated behind §6 step 5 + independent legal check │
 └─────────────────────────────────────────────────────────────┘
```

---

## 9. Phased roadmap

- **Phase 0 (done, 2026-07-02):** gather components, deep-research each, write this plan.
- **Phase 1 (done, 2026-07-03):** built the 8 prioritized data collectors (§2) against DuckDB
  storage, all live against real APIs. Corrections found while building: unlocks are DefiLlama
  paid-tier, and CryptoPanic has no free tier so it was swapped for the Alternative.me Fear & Greed
  index (see README collector table). No Firecrawl yet.
- **Phase 2 (done, 2026-07-03 → 2026-07-05):** designed the crypto Domain Pack (`ontology/crypto-pack/`
  — 15 object, 7 link, 21 action types), stood up the Open Foundry stack under Docker, and built the
  `raw_signals` → ontology migration bridge (`src/quiverquant/ontology/`). Tails closed: (a) graph
  link edges populated (a second migrate pass resolves endpoints by captured object id, then
  `createLink`); (b) the Firecrawl VC-portfolio collector (§3, `collectors/firecrawl_vc.py`) fills
  the `FundBacksProtocol` "who-backs-what" edges. Latest live graph: 570 vertices / 327 edges (226
  `FundBacksProtocol` from a16z/Paradigm/Dragonfly). Remaining §3 extension (non-blocking):
  token-unlock/vesting calendars.
- **Phase 3 (in progress):** integrate nautilus_trader, wire collected signals in as custom data,
  write and backtest first candidate strategy/strategies.
  - *Increment 1 (done):* data plumbing (`src/quiverquant/backtest/`). Historical OHLCV bars
    (CCXT `fetch_ohlcv`, DuckDB-cached — the Phase 1 CCXT collector only stored live ticker
    snapshots, useless for a backtest) and the Fear & Greed series (the only alt-data signal with
    real history today) both flow through the `BacktestEngine` as time-ordered `Bar` / custom
    `Data`, verified delivered with zero lookahead by a no-op observer strategy. No orders, no P&L.
    `uv run quiverquant backtest`.
  - *History backfill (done):* `src/quiverquant/backfill/` + `quiverquant backfill`. Turned the
    point-in-time collectors into real time series where the source exposes free history — Fear &
    Greed (3,073 daily, 2018+), DefiLlama per-protocol daily TVL (`tvl_history`, 27,709 rows, top 25
    non-CEX protocols, 2019+), and GitHub weekly dev-activity (`dev_activity_history`, 2,173
    repo-weeks, 4 repos, bitcoin back to 2009). Deduped, idempotent.
  - *Second signal (done):* aggregate daily DeFi TVL wired into the backtest as a `TvlData` custom
    stream beside Fear & Greed (`read_daily_tvl_total`).
  - *First real strategy (done):* Fear & Greed contrarian, long/flat on BTC/USDT with Binance 0.1%
    maker/taker fees + probabilistic slippage (`backtest/strategy.py`, `quiverquant backtest
    --strategy sentiment`). 2022-07→2026-07: +46% (83% win rate, 6 trades) vs +195% buy-&-hold —
    trails in a bull market because it holds cash through rallies. Reported as ending NET WORTH
    (USDT + BTC*last), since a CASH spot account with an open position at the end splits value across
    currency buckets; the raw per-currency PnL is misleading. Return-based ratios (Sharpe etc.) are
    unreliable here — too few trade days for a daily-return series.
  - *Next (Phase 4):* walk-forward + statistical-significance harness (§6 steps 2-3) to actually
    judge this and future candidates; add signals (TVL/dev-activity/regime) to the strategy.
- **Phase 4 (in progress):** built the qualification harness (§6 steps 2-3) on a shared windowed
  run primitive (`backtest/harness.py`): anchored walk-forward (`walkforward.py`, `quiverquant
  walkforward`) tunes thresholds in-sample and scores them out-of-sample; a Monte-Carlo permutation
  test (`significance.py`, `quiverquant significance`) shuffles Fear & Greed *values* across their
  timestamps to build a null return distribution (total-return statistic, since too few trades make
  Sharpe unreliable — see §9). The harness is strategy-pluggable and both gates take `--strategy`.
  **Two candidates judged, neither qualifies:**
  - *Candidate 1 — Fear & Greed contrarian:* beats buy-&-hold in only 1 of 4 out-of-sample folds
    (compounded OOS -27%), and its full-window +46% is statistically indistinguishable from the
    shuffled-signal null (200-perm p = 0.40; null mean +44% ≈ its own return — the apparent gain is
    bull-market drift a random signal captures equally).
  - *Candidate 2 — + DeFi-TVL momentum exit gate (`regime`):* revision hypothesis "don't sell into
    greed while aggregate DeFi TVL is above its 30-day MA" (the base sits out rallies). It lifts the
    in-sample full-window return to +171% and improves *both* gates — compounded OOS -20% (still 1/4
    folds beat buy-&-hold) and permutation p tightens to 0.16 — so the regime lever adds real,
    measurable value, but not enough to clear p≤0.05. Still fails §6.
  - *Candidate 3 — developer-activity momentum (`dev`):* an independent signal (long BTC while
    market-wide weekly commits across bitcoin/ethereum/solana/reth are above their MA). The harness
    was generalised to a strategy-agnostic param-dict grid to run it. **Strongest candidate yet:**
    first to be OOS-positive (compounded +11%, 3/4 folds positive, 2/4 beat buy-&-hold), and at the
    walk-forward-selected 26-week MA the full-window +175% has permutation p ≈ 0.09. But it is very
    window-sensitive (an 8-week MA overtrades to p ≈ 0.90, worse than noise), and scoring
    significance at the tuned window is mildly optimistic — verdict "promising, not qualified."
  - *Candidate 4 — crypto-news-sentiment contrarian (`news`):* fills the news/sentiment category
    (§2 #4) with a monthly net-sentiment series backfilled from the Perigon API (`news-backfill`,
    topic=Cryptocurrency, 54 months 2022-2026, stamped at month-close so no lookahead). Best
    walk-forward beat-count yet — 3/4 folds beat buy-&-hold (verdict "PASS-ish", compounded OOS
    +5.4%) — BUT two of those folds returned exactly 0.00% (it sat in cash), so the wins are
    drawdown-avoidance, and it missed a +55% up fold entirely; permutation p = 0.15, not
    distinguishable from shuffled sentiment. A drawdown-avoider, not a proven edge. (Also built:
    a forward crypto-news feed `quiverquant perigon`, Windows-scheduled daily, accumulating a finer
    series; and a `news-impact` event study — the biggest BTC crashes coincide with bearish news,
    e.g. FTX week, but sentiment sign predicts direction only ~coin-flip.)

  - *Candidate 5 — four-signal consensus ensemble (`ensemble`):* each signal votes bullish from its
    own rule (F&G fear, TVL momentum, dev momentum, news capitulation); hold BTC while ≥ `min_votes`
    agree, only that knob tuned. Weakest yet — walk-forward picked `votes≥1` every fold, degenerating
    to ~buy-&-hold (OOS +11%, 1/4 beat B&H); significance p = 0.55 (below the median of the
    shuffle-all-four-inputs null). Combining the weak signals produced no edge.

  **Gate scoreboard — 6 candidates, NONE qualify (all fail significance p≤0.05):** F&G 1/4 folds
  p=0.40 · regime 1/4 p=0.16 · dev 2/4 p=0.09 · news 3/4 p=0.15 · ensemble 1/4 p=0.55 ·
  cross-sectional momentum, survivorship-free walk-forward: 3/4 folds beat the random null,
  1/4 significant, compounded OOS −51% (the strongest *pattern* yet — see candidate 6 below —
  but a long-only alt book loses to the negative point-in-time tide).
  The gates are doing their job: every candidate that looked good in-sample (news +152%, dev +175%,
  ensemble +181%) was cut down out-of-sample or by the shuffled-signal null. **No single free signal,
  nor their consensus, shows a durable statistically-significant BTC daily-timing edge on 2022-2026.**
  The honest read is that free-data BTC market-timing may simply not carry a detectable edge at this
  cadence — future work should either change the target (cross-sectional alt book, longer horizon) or
  accumulate the finer forward series (news feed) before re-testing, not keep tuning daily BTC timing.

  **Lever #2 (graph features) built (`features/graph.py`, `quiverquant graph-features`):** VC
  conviction (projects backed by ≥2 distinct funds) + fund co-investment overlap from the
  `FundBacksProtocol` edges — 15 projects co-backed by a16z + Paradigm (Uniswap/Coinbase/Lido/…).
  It is cross-sectional as of the last scrape, so it does NOT yet feed the market-timing gates; it
  becomes tradeable via a cross-sectional long book (needs per-token OHLCV) or once repeated scrapes
  accumulate temporal backing history. See `research/open-foundry-strategic-advantage.md`.

  **Cross-sectional VC-conviction book — path 1, built and tested (`features/token_resolve.py`
  +`token_prices.py`+`cross_section.py`; `resolve-tokens`/`collect-prices`/`cross-section`):** the
  first backtest that actually *uses* the graph signal. `resolve-tokens` maps VC-backed names to
  liquid CoinGecko tokens (32/213 — most portfolio companies are equity/pre-token); `collect-prices`
  pulls daily history via **CCXT** (CoinGecko's `market_chart` now needs a Demo key; CCXT is keyless)
  — 29/32 tokens, 28k daily rows; `cross-section` runs an equal-weight high-conviction book vs BTC
  and a random-VC-subset permutation null. **Result: no edge (honest negative).** 2020-2026, the
  6-name conviction book −77% and the full 29-token VC book −29% vs BTC +195%; conviction did NOT
  beat random VC picks (p = 0.48, null mean +10%) — and this is *with* survivorship bias helping
  (current-holdings snapshot). Known caveats: daily-rebalance volatility drag (the conviction-vs-random
  comparison is apples-to-apples and robust to it), growing composition, homonym mismatches
  (Gensyn→AI, Rain→RAIN, Sky). Educational upper bound, not a qualified strategy.

  **Candidate 6 — cross-sectional momentum on a liquid-alt universe (`collect-universe` +
  `momentum`, 2026-07-07):** the first candidate after the "change the target" pivot — stop timing
  BTC, rank the top-80-mcap liquid alts (48 with CEX history ≥120d, stablecoins/wrapped/gold
  excluded) by trailing 90d return every 30d and hold the top 10 equal-weight. The null is random
  selection from the *same* universe, so the p-value isolates the ranking itself and is fair under
  the shared survivorship bias. Result 2017-11→2026-07 (106 rebalances): momentum book +5,212% vs
  random-book null mean +3,591% and equal-weight market +3,517% — directionally right (consistent
  with Liu-Tsyvinski-Wu, where momentum is a priced factor concentrated in large coins) but
  **p = 0.186, not distinguishable from random selection. Still fails §6.** The absolute numbers are
  upper bounds anyway: today's-liquid-set universe (survivorship), and coins dropping out mid-window
  are excluded from that window's book. Verdict: right target, unproven ranking — the next lever is
  data quality (point-in-time membership), not more parameter tuning.

  **Step 1 (survivorship-free dataset) DONE — both halves built, tested, and run for real
  (2026-07-07, commit 183db4a):**
  - **`backfill cmc-snapshots`** — coinmarketcap.com/historical/YYYYMMDD/ is server-rendered HTML,
    no login/JS needed (verified against real pages spanning 2015-2026). Top 20 rows carry full
    data; ranks 21-200 render as a locked "sign up to see more" teaser that still discloses rank
    position, slug, and name — enough for membership. One request per date, no rate limit hit.
    **Ran it: 104 monthly snapshots 2018-01→2026-06 into a new `universe_snapshot` table. 417
    distinct coins were EVER ranked top-80 across that window — vs. 48 in candidate #6's
    today's-liquid-only universe.** Confirmed real recoveries: BitConnect (rank 20, the 2018
    Ponzi scheme, one snapshot only), HEX, Terra/TerraUSD (gone by 2022-07), FTX Token (last top-80
    2024-01, tracking FTX's real decline), Waves (dropped 2022-09, its real de-peg crisis).
  - **`backfill binance-archive --symbol X/USDT`** — data.binance.vision is Binance's own public
    kline archive; append-only, so a pair's history survives delisting (the exact CCXT gap).
    Writes into the *existing* `ohlcv` table via `cache_ohlcv(exchange="binance", ...)` — no new
    schema, transparently merges with anything CCXT already cached. **Verified live: BTCST/USDT
    (delisted 2021 for wash-trading) backfilled 682 real daily bars, 2021-01-13→2022-11-28, that
    today's CCXT-only pipeline can no longer see at all.**
  - Full detail: `research/survivorship-free-universe.md`. Tests: `test_cmc_snapshots.py` (5),
    `test_binance_vision.py` (3), both pure-parse fixtures, no network. Suite 87/87.

  **Step 2 (re-run candidate #6 on the unbiased dataset) — DONE 2026-07-08 (commits e948232 +
  follow-ups). The headline: candidate #6's +5,212% was ENTIRELY survivorship bias.**
  Pipeline (`features/pit_universe.py` + `features/pit_momentum.py`; CLI `resolve-universe`,
  `collect-pit-prices`, `pit-momentum`, `pit-walkforward`):
  - *Resolution:* 301/417 members (72%) resolved to tickers. Two keys: CMC-slug == CoinGecko-id
    (the stronger one — recovers FTX Token→FTT, IMX, BAT, CRV where display names drifted), then
    normalized-name against CoinGecko's full `/coins/list` (includes delisted coins). Ambiguous
    collisions flagged.
  - *Pricing:* 247/301 priced (112 CCXT-live for survivors, 101 Binance-archive for dead coins
    bounded to their membership window — dodges the LUNA→Terra-2.0 reused-ticker trap; 54 gaps,
    genuinely unpriceable). **Median 72 of each snapshot's top-80 is tradeable, 84% avg coverage.**
    Found + fixed en route: Binance switched archive timestamps to microseconds in ~2025 files.
  - *Result, same config as candidate #6 (90d/30d/top-10, now with 10bps turnover fees):*
    **+5,212% (biased) → −44% (survivorship-free), p = 0.14.** Random top-10 books from the same
    point-in-time universe average −65%: the alt tide is deeply negative once dead coins are
    priced through their collapses. This one number quantifies the whole survivorship problem —
    the industry's "200-400% inflation" claim was a big understatement here.
  - *Cadence sweep (6 configs):* monthly holds all negative/insignificant, but the WEEKLY cadence
    the literature predicts (30d lookback / 7d hold) showed +45.9% vs null −78.5%, in-sample
    p = 0.003 (and 60/14: p = 0.010). Cherry-picked from a grid, so it went to walk-forward:
  - *Walk-forward (4 anchored folds, config chosen in-sample per fold, OOS scored vs fresh
    random null):* **still does NOT qualify.** The grid consistently chose 30/7 in every fold
    (the in-sample signal is stable) and 3/4 OOS folds beat the null mean — one decisively
    (2023-11→2025-03: +119.8% vs −16.2%, p = 0.005) — but compounded OOS is **−51%**: the
    ranking carries real information in bull regimes and drowns in bear/chop (fold 4:
    −66.6%, WORSE than null). Matches the literature's regime-dependence caveat exactly.
  - *Verdict:* honest fail, but the most informative one yet. The ranking isn't noise — it's
    long-only in an asset class whose point-in-time tide is strongly negative. The obvious NEXT
    hypothesis (new candidate, not a re-tune): make the book **regime-aware or long-short** —
    long top-K/short bottom-K momentum (market-neutral, harvests the ranking without the tide),
    or gate the long book to cash when a trend/regime filter is off. Both are new candidates for
    the gates, not free passes.

  **Ongoing regardless of step 2's timing:**
  - **Keep accumulating the forward series** that need calendar time, not code: daily Perigon
    news feed (scheduled), repeated Firecrawl VC-portfolio scrapes (builds the temporal backing
    history lever #2 needs), and the point-in-time feature store (lever #1, `ingested_at` on
    `raw_signals`).
  - **Path 2 (Wayback VC portfolios) parked** — feasibility proven, coverage thin (4/33
    snapshots); revisit only if an old-markup extractor becomes cheap, since candidate-#6-style
    price momentum doesn't depend on it.

  **Not yet done:** paper trading (§6 step 4) via nautilus_trader live-data mode and/or Co-Invest
  Computer simulation mode, once a candidate clears these gates.
- **Phase 5:** only after explicit, separately-discussed go-ahead — define live-promotion
  thresholds (§6 step 5), independently verify Liquid's legal standing or finalize direct
  Hyperliquid integration, and decide on real capital allocation. Not started, not implied by
  anything above.

## 10. Decisions (resolved 2026-07-02, before Phase 1)

- **Collector order:** the 8-source §2 order was confirmed as-is, no reprioritization.
- **Paid tiers:** build both a free and a paid tier per source (not free-only indefinitely) — free
  credits now, a paid upgrade path later, gated by env vars.
- **Engine:** nautilus_trader is the primary engine (not freqtrade).
- **Phase 5 live capital:** deferred — to be revisited only after Phase 4 paper-trading results
  exist, and only with a separate explicit go-ahead.
