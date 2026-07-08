# api.quiverquant.com (crypto alpha engine — research project)

**Status: Phase 1 complete (9 live collectors). Phase 2 (UNIFY layer) done — the
Open Foundry crypto Domain Pack loads on the running stack (Postgres 17 + Apache
AGE; full ODL semantic validation passed) and the migration bridge ingests stored
`raw_signals` rows into the ontology as governed-action calls. Both Phase 2 tails
are now closed: (a) graph link edges are populated (`WalletTransferredTo`,
`FundHoldsToken`, `ProtocolOnChain`, `TokenOnChain`, `ExchangeListsToken`), and
(b) Firecrawl-sourced VC-portfolio data now fills the `FundBacksProtocol`
"who-backs-what" edges. Latest verified live graph: 570 vertices / 327 edges
(incl. 226 `FundBacksProtocol` from a16z/Paradigm/Dragonfly portfolios).
**Phase 3 done** — the nautilus_trader `BacktestEngine` ingests historical price
bars (CCXT-sourced, DuckDB-cached) plus Fear & Greed and aggregate-TVL custom
`Data` streams time-ordered with no lookahead, and runs a first real strategy
(Fear & Greed contrarian, realistic fees + slippage). **Phase 4 started — the
qualification harness (§6 steps 2-3):** walk-forward validation and a
Monte-Carlo permutation significance test now judge candidate strategies out of
sample. First verdict on the Fear & Greed contrarian: **it does not qualify** —
it beats buy-&-hold in only 1 of 4 out-of-sample folds and is statistically
indistinguishable from a shuffled-signal null. See `PLAN.md` for the full roadmap.**

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
  - `backtest/` — Phase 3/4 nautilus_trader pipeline: `ohlcv.py` (CCXT historical
    bars → DuckDB), `signals.py` + `data.py` (`raw_signals` → custom `Data`),
    `observer.py` (no-op observer strategy), `strategy.py` (Fear & Greed
    contrarian), `run.py` (BacktestEngine wiring), and the Phase 4 qualification
    harness: `harness.py` (reusable windowed run primitive), `walkforward.py`
    (anchored walk-forward), `significance.py` (permutation test)
  - `backfill/` — Phase 3 historical backfills that turn point-in-time collectors
    into real time series (`defillama_tvl.py`; Fear & Greed reuses its collector)
  - `features/` — derived signals over the ontology data: `graph.py` (VC conviction
    + fund co-investment from `FundBacksProtocol`, lever #2 of
    `research/open-foundry-strategic-advantage.md`); `token_resolve.py` (VC name →
    CoinGecko token), `token_prices.py` (CCXT daily history), `cross_section.py`
    (equal-weight VC-conviction book vs BTC + random-subset null — path 1)
- `ontology/crypto-pack/` — Open Foundry external Domain Pack (the UNIFY layer)
- `deploy/` — how to stand up Open Foundry with the crypto pack mounted
- `.env.example` — every API key a collector can use, and which sources need none
- `data/` — local DuckDB file, gitignored

## Running collectors

```
uv sync
uv run quiverquant                       # run all 9 collectors
uv run quiverquant defillama ccxt        # run specific ones
uv run quiverquant migrate-ontology --dry-run   # Phase 2: preview ontology ingestion
uv run quiverquant backtest                      # Phase 3: plumbing backtest (observer, 3 streams)
uv run quiverquant backtest --strategy sentiment # Phase 3: Fear & Greed contrarian strategy (with fees)
uv run quiverquant backtest --strategy regime    # Phase 4: + DeFi-TVL momentum exit gate
uv run quiverquant backfill fear-greed           # Phase 3: full Fear & Greed history (2018+)
uv run quiverquant backfill defillama-tvl --top 25     # Phase 3: daily TVL history per top protocol
uv run quiverquant backfill dev-activity         # Phase 3: weekly commit history per repo
uv run quiverquant backfill cmc-snapshots --start 2018-01-01   # §9 step 1: point-in-time top-200 universe (CoinMarketCap)
uv run quiverquant backfill binance-archive --symbol BTCST/USDT  # §9 step 1: delisted-pair daily klines (data.binance.vision)
uv run quiverquant resolve-universe --refresh     # §9 step 2: snapshot members -> tickers (CoinGecko full list)
uv run quiverquant collect-pit-prices             # §9 step 2: price members (archive-first for dead coins)
uv run quiverquant pit-momentum                   # §9 step 2: survivorship-free momentum vs random null (fees incl.)
uv run quiverquant pit-walkforward                # §9 step 2: anchored walk-forward over the pit universe
uv run quiverquant walkforward --strategy dev --splits 4      # Phase 4: anchored walk-forward (sentiment|regime|dev)
uv run quiverquant significance --strategy dev --permutations 200  # Phase 4: shuffled-signal permutation test
uv run quiverquant graph-features                # Lever #2: VC-conviction / co-investment from FundBacksProtocol edges
uv run quiverquant resolve-tokens                # Path 1A: map VC-backed names -> liquid CoinGecko tokens
uv run quiverquant collect-prices                # Path 1B: daily price history for resolved tokens (via CCXT)
uv run quiverquant cross-section                 # Path 1C: cross-sectional VC-conviction book (survivorship-biased)
uv run quiverquant perigon                        # Perigon: incremental crypto-news feed (~1 call; daily-scheduled)
uv run quiverquant news-backfill                  # Perigon: backfill monthly sentiment series (~1 call/month)
uv run quiverquant news-impact --top 10           # Perigon: did news move BTC? biggest move days vs that day's news
uv run quiverquant walkforward --strategy news    # Phase 4: news-sentiment candidate through the gates
uv run quiverquant wayback-vc --extract           # Path 2: point-in-time VC portfolios from archive.org
uv run quiverquant collect-universe --top 80      # Option 1: top-N liquid-alt universe prices via CCXT (--resume after a rate-ban)
uv run quiverquant momentum                       # Option 1: cross-sectional momentum vs random-selection null (candidate #6)
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
| 9 | Firecrawl (VC portfolios) | `firecrawl_vc.py` | Live — scrapes a16z/Paradigm/Dragonfly/etc. portfolio pages via Firecrawl `/scrape` JSON extraction (keyless works; `FIRECRAWL_API_KEY` lifts limits), deduped against stored (fund, company) pairs → `FundBacksProtocol` edges |

## Phase plan

- **Phase 0 (done):** gather components, research each, produce `PLAN.md`
- **Phase 1 (done):** data collectors above
- **Phase 2 (done):** Open Foundry crypto Domain Pack (`ontology/crypto-pack/`)
  loads on the live stack (`deploy/`) and the migration bridge
  (`src/quiverquant/ontology/`) ingests `raw_signals` → governed-action calls,
  including graph link edges. Both tails closed: graph link edges populated, and
  Firecrawl VC-portfolio data fills the `FundBacksProtocol` edges (collector #9).
  Remaining Firecrawl extension (not blocking): token-unlock/vesting calendars
- **Phase 3 (in progress):** nautilus_trader integration.
  - Increment 1 done — data plumbing: historical bars + Fear & Greed custom data
    flow through the `BacktestEngine` time-ordered (`uv run quiverquant backtest`),
    no-op observer strategy, no orders/P&L.
  - History backfill done — `raw_signals` now holds three real multi-year series:
    Fear & Greed (3,073 daily, 2018+), DefiLlama TVL (27,709 points, 25 protocols,
    2019+), and GitHub dev-activity (2,173 repo-weeks, 4 repos, bitcoin back to
    2009). Aggregate DeFi TVL is wired into the backtest as a second custom-data
    signal alongside Fear & Greed.
  - First real strategy done — Fear & Greed contrarian (long/flat on BTC/USDT,
    Binance 0.1% maker/taker fees + probabilistic slippage). Over 2022-07→2026-07
    it returned +46% (83% win rate, 6 trades) vs +195% buy-&-hold — it sits in
    cash during rallies, so it trails in a bull market. NOT qualified — it's the
    first candidate for the Phase 4 §6 gates (walk-forward, significance).
- **Phase 4 (in progress):** the qualification harness — walk-forward + statistical
  significance (§6 steps 2-3), then paper trading (§6 step 4).
  - Walk-forward + significance harness done (`backtest/harness.py`,
    `walkforward.py`, `significance.py`; `uv run quiverquant walkforward` /
    `significance`). Anchored walk-forward tunes thresholds in-sample and scores
    them out-of-sample; the permutation test shuffles Fear & Greed values across
    their timestamps to build a null return distribution.
  - **Candidate 1 — Fear & Greed contrarian — does NOT qualify:** out-of-sample
    it beats buy-&-hold in only 1 of 4 folds (compounded OOS -27%), and over the
    full window its +46% is indistinguishable from a shuffled-signal null
    (permutation p = 0.40, null mean +44% ≈ the strategy's own return — its
    "edge" is just bull-market drift).
  - **Candidate 2 — + DeFi-TVL momentum exit gate (`--strategy regime`) — better
    but still does NOT qualify:** holding through greed while aggregate TVL is
    above its 30-day average lifts the in-sample full-window return to +171%
    (vs +46%), and it improves *both* gates — 1/4 folds still beat buy-&-hold but
    compounded OOS rises to -20%, and the permutation p-value tightens to 0.16
    (vs 0.40). The gate adds real, measurable value, but not enough to clear
    p≤0.05. Back to revision per §6.
  - **Candidate 3 — developer-activity momentum (`--strategy dev`) — the
    strongest yet, still short of the bar:** long BTC while market-wide weekly
    commit volume (bitcoin/ethereum/solana/reth) is above its moving average — an
    independent signal from price and sentiment. Out-of-sample it is the first
    candidate to be *positive* (compounded OOS +11%, 3/4 folds positive, **2/4
    beat buy-&-hold**), and at the walk-forward-selected 26-week MA the full-window
    +175% has a permutation p ≈ 0.09. But it's highly window-sensitive (a naive
    8-week MA overtrades to p ≈ 0.90, *worse* than noise), and testing significance
    at the tuned window is mildly optimistic — so "promising, not qualified."
  - **Candidate 4 — crypto-news-sentiment contrarian (`--strategy news`) — best
    walk-forward yet, still fails significance:** a monthly crypto-news net-sentiment
    series backfilled from Perigon (`news-backfill`, topic=Cryptocurrency, 54 months)
    drives a contrarian (long on bad-news capitulation, cash on euphoria). It beats
    buy-&-hold in **3/4** out-of-sample folds (a first — verdict "PASS-ish", compounded
    OOS +5.4%), but two of those folds returned exactly 0.00% (it sat in cash), so the
    "wins" are drawdown-avoidance and it missed a +55% up fold entirely; permutation
    **p = 0.15** — not distinguishable from shuffled sentiment. A drawdown-avoider, not
    a proven edge.
  - **Candidate 5 — four-signal consensus ensemble (`--strategy news`… `ensemble`) —
    weakest of all:** each signal votes bullish from its own rule; hold BTC while ≥
    `min_votes` agree (only that knob is tuned). Walk-forward picked `votes≥1` every
    fold → degenerates to ~buy-&-hold (compounded OOS +11%, 1/4 beat B&H); stricter
    consensus churns. Significance **p = 0.55** — 109/200 shuffled-input versions beat
    it, i.e. below the *median* of noise. Combining the weak signals produced no edge.
  - **Graph-derived VC-conviction features (`uv run quiverquant graph-features`)** —
    lever #2 from the Open Foundry research, built as `features/graph.py`: computes
    VC conviction (projects backed by ≥2 distinct funds) and fund co-investment
    overlap from the `FundBacksProtocol` edges. Real output (15 projects co-backed
    by a16z + Paradigm: Uniswap, Coinbase, Lido, Optimism, dYdX…). **Cross-sectional
    as of the last scrape, so it does not yet feed the market-timing gates** — it's a
    screening signal until we add per-project token prices (a cross-sectional book)
    or accumulate temporal backing history.
  - **Cross-sectional VC-conviction book (path 1) — no edge, honest negative.**
    `resolve-tokens` maps VC-backed names to liquid CoinGecko tokens (32/213 — most
    are equity/pre-token), `collect-prices` pulls daily history via CCXT (29/32,
    28k rows), and `cross-section` backtests an equal-weight high-conviction book
    (names backed by ≥2 funds) vs BTC + a random-VC-subset null. Over 2020-2026 the
    6-name conviction book returned **−77%** and the full 29-token VC book −29%, vs
    **BTC +195%**; conviction did **not** beat random VC picks (**p = 0.48**) — and
    that's *with* survivorship bias helping. Caveats: daily-rebalance volatility drag,
    growing composition, a few homonym mismatches. The honest fix is path 2.
  - **Candidate 6 — cross-sectional momentum on a liquid-alt universe
    (`collect-universe` + `momentum`) — right target, unproven ranking.** The pivot
    off BTC timing: rank the top-80-mcap liquid alts (48 with ≥120d CEX history;
    stablecoins/wrapped/gold excluded) by trailing 90d return every 30d, hold the
    top 10 equal-weight. The null is random selection from the *same* universe, so
    the p-value isolates the ranking and is fair under the shared survivorship
    bias. 2017-11→2026-07 (106 rebalances): momentum book **+5,212%** vs random-book
    null mean +3,591% / equal-weight market +3,517% — directionally consistent with
    the academic momentum factor (Liu-Tsyvinski-Wu), but **p = 0.186: not
    distinguishable from random selection. Still fails §6.** Absolute numbers are
    survivorship-inflated upper bounds regardless.
  - **Survivorship-free dataset — collection DONE (`backfill cmc-snapshots` +
    `backfill binance-archive`).** Point-in-time universe membership from CoinMarketCap's
    `/historical/YYYYMMDD/` pages (server-rendered HTML, no login/JS needed): a monthly
    backfill 2018-01→2026-06 (104 snapshots, 0 failures) found **417 distinct coins ever
    ranked top-80** — vs. 48 in candidate 6's today's-liquid-only universe. Real recoveries:
    BitConnect (rank 20, gone within weeks of Jan 2018), HEX, Terra/TerraUSD (gone by
    2022-07), FTX Token (gone by 2024-01), Waves (dropped 2022-09). Dead-coin price history
    from Binance's public `data.binance.vision` kline archive (append-only, survives
    delisting) — verified live on BTCST/USDT (delisted 2021): 682 real daily bars CCXT can
    no longer see, written straight into the existing `ohlcv` table.
  - **Candidate 6 re-run on the unbiased dataset (`resolve-universe` → `collect-pit-prices`
    → `pit-momentum` / `pit-walkforward`) — THE decisive result: +5,212% was entirely
    survivorship bias.** 301/417 members resolved to tickers (CMC-slug==CoinGecko-id first,
    then name match against the full `/coins/list` — never `/coins/markets`, which would
    reintroduce the bias); 247 priced (survivors CCXT-live, dead coins Binance-archive
    bounded to their membership window — dodges the LUNA→Terra-2.0 reused-ticker trap);
    median 72 of each snapshot's top-80 tradeable (84% coverage). Same config as candidate
    6, now with point-in-time membership + 10bps turnover fees: **−44% (p=0.14)**, and random
    top-10 books from the same universe average −65% — the alt tide is deeply negative once
    dead coins are held through their collapses. A cadence sweep found the literature's
    weekly momentum (30d/7d: +45.9%, in-sample p=0.003), so it went to walk-forward: the
    grid chose 30/7 in every fold and **3/4 OOS folds beat the random null** (one at
    p=0.005, +119.8% vs −16.2%) — the strongest pattern of any candidate — but compounded
    OOS is **−51%**: real ranking information, drowned by holding long-only alts through
    bear/chop regimes. Still fails §6. Next candidate (new hypothesis, not a re-tune):
    long-short (long top-K / short bottom-K, market-neutral) or a regime-gated long book.
    Meanwhile the forward series keep accumulating (daily Perigon news feed, repeat
    VC-portfolio scrapes).
  - **Final scoreboard — 6 candidates, none qualify** (all fail significance p≤0.05):
    F&G 1/4 folds p=0.40 · regime 1/4 p=0.16 · dev 2/4 p=0.09 · news 3/4 p=0.15 ·
    ensemble 1/4 p=0.55 · cross-sectional momentum (survivorship-free walk-forward)
    3/4 folds beat the random null, 1/4 significant, compounded OOS −51% — the strongest
    pattern of any candidate. **No single free signal, nor their consensus, shows a
    statistically-significant edge that survives an honest test** — the framework cut
    down every in-sample winner (news +152%, dev +175%, ensemble +181%, momentum
    +5,212%→−44% once survivorship bias was removed) out-of-sample or against a
    shuffled/random null, rather than shipping an overfit or fabricated-by-bias strategy.
    A forward crypto-news feed (`quiverquant perigon`, Windows-scheduled daily) and the
    survivorship-free universe both keep accumulating for future re-tests.
- **Phase 5 (not started, gated):** live capital — explicit separate go-ahead required
