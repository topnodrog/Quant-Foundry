# Strategic advantage from Open Foundry — grounded capability review

**Date:** 2026-07-06. **Scope:** where the Open Foundry platform
(`syzygyhack/open-foundry`, cloned at `C:\dev\open-foundry`) can give this
project an edge that a flat DuckDB `raw_signals` table cannot — grounded in the
platform's *actual* features (`README.md`, `docs/open-foundry-spec-v2.md`), not
generic graph-database marketing.

Read alongside `research/github-openfoundry-nautilus.md` (why OF was picked as
the UNIFY layer) and `PLAN.md` §4/§6. This doc is specifically about **offense**:
turning the ontology from passive storage into a source of alpha and rigor.

---

## 0. TL;DR — honest ranking

We already run the hard part (a live OF stack with a 15-object crypto pack, 570
graph vertices / 327 edges). Almost none of OF's *derivation and temporal*
machinery is switched on yet. Ranked by return-on-effort for a solo researcher:

| # | Lever | Edge it buys | Effort | Verdict |
|---|---|---|---|---|
| 1 | **Point-in-time / temporal queries** (`getObjectAtTime`, versioning, lineage) | Lookahead-free feature store — directly hardens the Phase 4 gates | Low–Med | **Build first** |
| 2 | **Graph-derived features** (`@function` / `@computed`) | Relationship signals no single collector produces (co-investment, fund-flow centrality, smart-money proximity) | Med | **Build second** |
| 3 | **Event-driven signals** (CEL action side-effects → CloudEvents bus) | Cross-source triggers as a *live* alt-data feed for paper trading | Med | Stage with §6 step 4 |
| 4 | **Data-quality rules** (cross-object + time-window `expr`) | Anomaly/divergence detection as its own signal + data hygiene | Low | Cheap win, do alongside 2 |
| 5 | **GraphQL subscriptions / object sets / full-text** | Live universes, research/live parity, filing/news search | Low | Opportunistic |

The two that produce *signal we literally cannot get otherwise* are **#1 and
#2**. Everything else is amplification. The rest of this doc is the evidence.

---

## 1. What "strategic advantage" means here

Two distinct edges, both real:

- **Alpha edge** — signals a competitor scraping the same free sources into flat
  tables *cannot* compute, because they require (a) the *relationships* between
  entities or (b) knowing *exactly what was true at a past instant*. The graph
  and the temporal engine are the only reasons to pay OF's operational cost.
- **Rigor / defensibility edge** — reproducible, point-in-time-correct,
  provenance-tracked research. This is what lets us honestly claim a strategy is
  "qualified" (the whole framing of `PLAN.md` §0/§6) rather than curve-fit. It
  also matters for the fundraising narrative: "every backtest traces to exact
  source data and mapping version" is a credibility asset.

QuiverQuant's entire product is *derived* alt-data. Our version of that
derivation lives in the ontology layer — if we leave it as dumb storage we've
paid the Docker/AGE tax for nothing.

---

## 2. Lever #1 — Temporal queries = a lookahead-free feature store

**The capability (spec §3, §4.6):** the SPI exposes
`getObjectAtVersion(type, id, version)` and `getObjectAtTime(type, id, timestamp)`;
`QueryOptions` carries `asOfTime` / `asOfVersion`; every non-system field write
emits an immutable `FieldProvenance` record (`source: ACTION | SYNC | FUNCTION`,
with `producedAt`, `mappingVersion`, `sourcePointer`). Objects and links are
versioned monotonically with soft-delete history.

**Why it's the #1 edge for *this* project:** our entire Phase 4 harness exists to
avoid lookahead bias. Right now we dodge it crudely — only Fear & Greed and TVL
have honest daily history, and everything else is a point-in-time snapshot we
can't safely backtest (see the "KEY DATA REALITY" note in the project memory /
`PLAN.md` §9). A temporal ontology flips that: **as the collectors run over
time, OF accumulates a versioned history of every entity's state**, and
`asOfTime` lets a backtest ask "what did we know about protocol X / wallet Y on
this date?" — provably excluding anything learned later. That is the textbook
definition of a point-in-time-correct feature store, and it is the single
biggest methodological advantage a serious quant setup has over a retail one.

**Concrete uses:**
- Backtest features derived from slowly-changing entity state (a protocol's VC
  backing count, a wallet's smart-money label, a token's chain) *as of the bar
  date*, not as of today — no leakage.
- Lineage answers "why did the strategy trade here?" down to the source row and
  mapping version — audit trail for the qualification claim.
- Provenance also exposes *when we learned* something vs. *when it was true*,
  which is exactly the arrival-time modeling nautilus's custom-data bus wants.

**Caveat (be honest):** temporal correctness only helps for data we *started
capturing before the backtest window*. It does not retroactively create history
we never collected. So the payoff compounds from now forward — which is an
argument to turn it on early, not a reason it's not worth it. For pre-existing
free history (DefiLlama TVL charts, GitHub commit weeks) we still backfill.

---

## 3. Lever #2 — Graph-derived features via `@function` / `@computed`

**The capability (spec §2.1.5, §2.3, §4.4):**
- `@function(runtime: "typescript" | "python", entry: ...)` — named, sandboxed,
  **read-only** computations over the ontology, compiled into the GraphQL/REST
  API. No state mutation (that's actions' job); ideal for feature extraction.
- `@computed(fn, cache: EAGER | LAZY | TTL, ttl)` — materialized derived fields
  on entities, auto-invalidated on writes (EAGER does dependency tracking).
  Built-ins include `countLinks`, `sumField`.
- Graph traversal is AGE-backed with depth (10) and node (10,000) guards, and
  `traverse(startId, path)` walks typed multi-hop paths.

**Why it's an edge:** these are *relationship* signals. A flat table has whale
transfers, VC portfolios, and TVL as separate columns; the graph has them as a
connected structure you can walk. Features that need the edges:

- **VC conviction / co-investment clustering** — `Fund -backs-> Protocol` is
  already populated (226 edges from a16z/Paradigm/Dragonfly). A `@computed`
  `Protocol.backingScore` = weighted count of distinct top-tier funds backing
  it; a `@function` that finds protocols backed by ≥N of the same funds
  (co-investment cliques) — a known lead indicator of the "smart money is
  clustering here" pattern before TVL/price moves.
- **Smart-money proximity** — multi-hop `Wallet -transferred_to-> Wallet`
  traversal to score how many hops a token/protocol is from a labelled
  smart-money wallet; concentration of smart-money holdings via
  `Fund -holds-> Token`.
- **Fund-flow network centrality** — degree/reach of a wallet in the transfer
  graph as a proxy for "hub" exchange-deposit or market-maker addresses.
- **Cross-source confirmation** — a `@function` that returns protocols where
  dev-activity is rising *and* VC backing is high *and* TVL is inflecting: a
  composite that no single collector emits.

These become new columns in `raw_signals` (via a periodic "derive graph
features" job that reads the `@function`/`@computed` outputs) and therefore new
custom-data streams for the nautilus backtest — feeding straight into the
task #6 multi-signal strategy work.

**Caveat:** graph features need enough *populated* edges to be non-trivial. We
have VC-backing and some transfer/holding edges; wallet-transfer coverage is
thin (22 edges). So the first graph features to build are the VC-backing ones
(dense) before the wallet-graph ones (sparse until we run collectors longer).

---

## 4. Lever #3 — Event-driven signals (CEL actions → CloudEvents bus)

**The capability (spec §4.2, §5.1):** every action runs a pipeline
(validate → authorize → consent → **preconditions (CEL)** → effects →
**side-effects** → audit → **emit**). Side-effects can be `webhook` or `event`;
the engine also emits CloudEvents for every object/link change to a
Redpanda/Kafka bus (in-memory fallback single-pod), partitioned and ordered by
version, with a dead-letter queue.

**We already do a little of this:** `RecordWhaleTransfer` emits
`crypto.whale.transfer` — but nothing consumes it. The strategic move is to make
the ontology a **signal generator at write time**, then subscribe the strategy
engine to that stream.

**Concrete uses:**
- CEL-precondition-gated events: emit `crypto.smartmoney.cex_deposit` only when
  `params.fromLabel` is a VC/fund *and* `params.toLabel` is a CEX deposit
  address *and* `amountUsd > threshold` — a classic "insider is about to sell"
  leading indicator, computed inside the action, not in ad-hoc Python.
- These CloudEvents are exactly a live alt-data feed. When we reach **§6 step 4
  (paper trading)** the *same* ontology that produced backtest features streams
  live events into nautilus's live-data mode — research/live parity, mirroring
  nautilus's own design principle. That parity is a genuine edge over a
  backtest-only pipeline that has to be re-implemented for live.

**Verdict:** high value but its natural home is the paper-trading stage. Build
the event *emission* opportunistically now (cheap — it's YAML), wire *consumption*
when §6 step 4 starts.

---

## 5. Lever #4 — Data-quality rules as a divergence signal

**The capability (spec §4.7):** register cross-object, time-windowed rules
(`scope`, `window: "PT4H"`, CEL `expr` over related objects), which emit
`openfoundry.quality.violation` events with severity and evidence. Non-blocking
by default.

**Dual use:** these were designed for data hygiene ("occupancy > capacity"), but
for us a "quality violation" *is* a market signal: a rule like "TVL dropped >30%
in PT24H while dev-activity is flat" or "a token unlock is <7 days out and
smart-money holdings are falling" is a divergence/anomaly detector expressed
declaratively. Same machinery, emits the same subscribable events as lever #3.
Cheap to add (YAML rules), so pair it with lever #2.

---

## 6. Lever #5 — Subscriptions, object sets, full-text (opportunistic)

- **GraphQL WebSocket subscriptions** — real-time object-change stream; the
  read-side twin of the event bus for a live dashboard / paper-trading monitor.
- **Object sets** (spec / README) — named persistent collections. Encode reusable
  strategy *universes*: "smart-money wallets", "top-VC-backed protocols",
  "tokens with unlocks in 30d" as first-class sets to iterate strategies over.
- **Full-text search** (`tsvector`, `@searchable`) — we already mark
  `RegulatoryFiling` / names searchable; a search over enforcement filings + news
  is a fast sentiment/risk lookup without a separate index.

All low-effort, none game-changing alone — adopt as they become convenient.

---

## 7. What we are *not* using yet (gap list)

Against our live `ontology/crypto-pack`: we have 15 object types, 7 link types,
~21 register/record/link actions, flat ReBAC roles, and **one** event side-effect
(`crypto.whale.transfer`, unconsumed). We use **none** of:

- `getObjectAtTime` / `asOfTime` temporal reads (lever #1)
- `@function` computations (lever #2)
- `@computed` fields (lever #2)
- CEL preconditions beyond `hasRole` + a null check (lever #3)
- event side-effects on any action except whale-transfer (lever #3)
- data-quality rules (lever #4)
- object sets, subscriptions, full-text queries in the pipeline (lever #5)

Every item above is switched off, not missing. The platform already supports all
of them; this is unrealized capability, not new engineering on OF itself.

---

## 8. Recommended sequence (fits the existing roadmap)

1. **Now, alongside task #6 (multi-signal strategy):** add the first
   **graph-derived features** — a `@computed Protocol.backingScore` and a
   `@function` for co-investment cliques over the dense `FundBacksProtocol`
   edges — and a small "derive graph features → `raw_signals`" job so they
   become nautilus custom-data streams the strategy and the Phase 4 gates can
   test. Add 1–2 **data-quality divergence rules** in the same pass (cheap).
2. **Next:** stand up the **point-in-time feature read** — a thin
   `asOfTime` query path so backtest features pull entity state as-of the bar
   date. Start capturing versioned history now so it compounds.
3. **With §6 step 4 (paper trading):** wire **event consumption** — subscribe
   nautilus live-data mode to the CloudEvents bus so the same ontology feeds
   both backtest and live. Add the CEL-gated `crypto.smartmoney.cex_deposit`
   emission.

**Honest bottom line:** for a single-researcher project most of OF's operational
surface (Helm, HPA, federation, consent, FHIR) is irrelevant. But two of its
capabilities — **temporal/point-in-time correctness** and **graph-derived
relationship features** — are exactly the two things that (a) produce alpha a
flat-table competitor can't and (b) make the "rigorously qualified" claim in
PLAN.md §0 defensible. Those are the reasons to have paid the ontology tax, and
they're currently unrealized. Turn them on.
