# Strategy/Execution Engine Research: "OpenFoundry" and nautechsystems/nautilus_trader

Research date: 2026-07-02
Scope: crypto-relevant capabilities only, as inputs to the `api.quiverquant.com` alternative-data project's strategy/execution layer.

---

## 1. "OpenFoundry" — CONFIRMED: [syzygyhack/open-foundry](https://github.com/syzygyhack/open-foundry)

**Update (2026-07-02): the user provided the actual URL.** The original search pass (below, preserved for reference) could not find a confident trading-relevant match — correctly so, because the real target is a **semantic ontology / operational "digital twin" platform**, not a trading tool at all. This changes its role in the architecture from "strategy/execution engine" to **data-integration/ontology backbone**.

**What it actually is:**
- Open-source platform for building operational digital twins via semantic ontology modeling — a Palantir Foundry-style system: queryable, actionable models of real-world entities and their relationships, extended via composable "Domain Packs."
- **Tech stack:** TypeScript (97.2%) + Go (1.5%, CEL expression evaluator sidecar); PostgreSQL 17 + Apache AGE (graph extension) for storage, or in-memory.
- **APIs:** GraphQL (Apollo) and REST, with FHIR R4 support (healthcare interop standard) built in.
- **Key subsystems:** Ontology Definition Language (ODL) for schema; OpenFGA for relationship-based access control; a CEL-expression action framework for triggering behavior on data changes; multi-tenant architecture with audit trails; Docker/Kubernetes/Helm deployment; OpenTelemetry observability.
- **License:** Apache 2.0 — permissive, no copyleft concerns, safe to build on or extend.
- **Activity:** 36 stars, 13 forks, 212 commits on main, active development as of research date.
- **Existing domain packs:** healthcare (NHS Acute), AML (anti-money-laundering) compliance, supply chain — no crypto/finance domain pack exists today, but AML is directly adjacent to the project's "regulatory/gov" alt-data category.

**Role fit for this project — repurpose, don't discard:** Open Foundry has zero built-in crypto or trading logic, but its actual capability — model heterogeneous entities (wallets, protocols, tokens, VCs, exchanges, people) and their relationships in a queryable ontology, ingest data via GraphQL/REST, and trigger actions via CEL rules on changes — is a strong match for the project's hardest non-trading problem: **unifying data from a dozen disparate free sources (on-chain, sentiment, VC flows, regulatory filings, dev activity) into one coherent, queryable model** before any strategy engine consumes it. This reframes Open Foundry as the **data/ontology layer sitting between the collectors and nautilus_trader**, not a competitor to nautilus_trader. A custom "crypto" Domain Pack would need to be built (wallets, protocols, tokens, unlock events, whale transfers as ontology objects/relationships) — real but scoped work, not a blocker.

<details>
<summary>Original search pass (preserved — the ambiguity was real before the URL was confirmed)</summary>

There is no "OpenFoundry" GitHub project findable by name search alone that is meaningfully relevant to quant trading, crypto strategy, or AI-agent-driven markets work. The name collides with several unrelated products, all in the "Palantir Foundry alternative" / "AI dev tooling" space, and `syzygyhack/open-foundry` specifically did not surface in general "OpenFoundry" searches (likely due to the hyphenated repo name and low star count at the time). This is a good example of why guessing from a name alone is risky — the correct repo existed the whole time, just not prominently indexed for generic queries.

### Candidates found (ranked by relevance signal, not stars)

| Repo/Org | Stars | Language | Description | Last activity | Crypto/trading relevance |
|---|---|---|---|---|---|
| [bsamud/openfoundry-agentic-framework](https://github.com/bsamud/openfoundry-agentic-framework) | 32 | Python | "Protocol-first, DAG-executing, multi-provider AI agent orchestration framework" with Forge/Conveyor/Shield/Watchtower modules (SDLC + CI/CD + guardrails + observability for AI agents) | ~Mar 2026, 182 commits, MIT license | **None.** Generic multi-agent orchestration for software engineering workflows (build/deploy/monitor AI agents), not markets or finance. Could theoretically host a trading agent as a workload, but has zero finance-specific code, docs, or examples. |
| [u485349-coder/OpenFoundry](https://github.com/u485349-coder/OpenFoundry) | 27 | Rust | Open-source Palantir Foundry alternative: connect data sources, build ontologies, pipelines, dashboards, "AI-powered decisions," self-hosted | Apr 2026, AGPL-3.0-only, 42 Go microservices + React console | **None directly**, but conceptually closest to "useful infrastructure" — a generic ontology/pipeline/dashboard data platform *could* in principle be repurposed to house crypto alt-data pipelines, the same way one might use Palantir Foundry for any domain. No crypto/trading features exist today. AGPL-3.0 is also a much stronger copyleft than LGPL, a real consideration if ever adopted. |
| [Shadowfax-Data/OpenFoundry](https://github.com/Shadowfax-Data/OpenFoundry) | 27 | TypeScript/Python | "Fastest way to build data products with AI" — AI-assisted dashboards/notebooks/data apps, connects to Snowflake/Databricks/BigQuery/ClickHouse/Postgres | Aug 2025, Apache-2.0 | **None.** BI/data-app builder for enterprise warehouses, not a trading or crypto tool. No exchange connectivity, no strategy/backtest concepts. |
| [Przyval/openfoundry](https://github.com/Przyval/openfoundry) | 9 | TypeScript | Fork/variant of the ontology-first "Palantir alternative," "100% @osdk/foundry SDK compatible" | Mar 2026, Apache-2.0 | **None.** Same category as u485349-coder's repo. |
| [Shamdon/openfoundry](https://github.com/Shamdon/openfoundry) | 0 | — | Fork of u485349-coder/OpenFoundry | — | **None.** Zero-star fork, no independent development. |
| [openfoundry-ai](https://github.com/openfoundry-ai) (org) → `model_manager` | 343 | Python | "Simplifies deploying an open source AI model to your own cloud" — the org behind openfoundry.ai | Last updated May 2024, MIT license | **None.** Generic OSS-LLM deployment tooling (model hosting/serving), not trading. This is likely the "real" OpenFoundry brand (highest legitimacy/star count of anything using the name) but it's an AI infra company, not a quant tool. |

### Possible confusions (checked, ruled out or noted for awareness)

Search for "OpenFoundry" + trading/crypto/hedge-fund repeatedly surfaced **other, differently-named** projects that a note-taker or LLM could plausibly misremember as "OpenFoundry":
- `OpenFinClaw` — described in search results as an "AI-native hedge fund platform" with a Rust backtesting engine and natural-language strategy generation. Not independently verified in this pass (out of the requested scope), but worth a dedicated look if the project wants an AI-agent-native crypto hedge-fund tool — name is close enough to be a mix-up source.
- `AutoHedge` (The-Swarm-Corporation) — "autonomous hedge fund" via swarm AI agents.
- `QuantHedgeFund` (Ashutosh0x and separately jarmni) — already flagged as a separate TBD item in the project README; not "OpenFoundry" but easy to conflate.
- `TradingAgents` (TauricResearch), `AI-Trader` (HKUDS), `ai-hedge-fund` (virattt), `QuantDinger` — all legitimate multi-agent LLM trading frameworks that turned up organically while searching, none named OpenFoundry.

**Recommendation (superseded — see confirmed section above):** this originally called for going back to the source for a URL. That happened; `syzygyhack/open-foundry` is confirmed and repurposed as the ontology/data-integration layer.

</details>

---

## 2. nautechsystems/nautilus_trader

Repo: https://github.com/nautechsystems/nautilus_trader
Docs: https://nautilustrader.io/docs/latest/
Backed by: Nautech Systems Pty Ltd (Australia) — offers OSS, "Pro," managed Cloud, and Institutional support tiers on top of the same open-source core.

### Architecture overview

- **Rust-native core** (70.7% of codebase) with a Python control/strategy layer (22.8%) and a thin Cython binding layer (5.5%) — Cython usage appears to be shrinking as more of the system migrates to Rust with PyO3 bindings.
- Single **event-driven architecture** shared by both backtesting and live trading: the same `Strategy`/`Actor` classes, order/event objects, and execution semantics run unchanged in `BacktestEngine`/`BacktestNode` (research) and in live trading gateways — this "research-to-production parity" is the project's core value proposition and directly reduces backtest-to-live drift risk, which matters a lot for a strategy meant to be "continuously re-qualified."
- Nanosecond-resolution timestamping, deterministic simulation, and a matching engine that can operate at multiple data fidelities (see backtesting section below).
- Ships as an installable Python package (`pip install nautilus_trader`) backed by compiled Rust/Cython extensions — not something you fork and modify in place; you consume it as a dependency and write strategies against its API.

### Crypto exchange integrations

All integrations are delivered as modular "adapters." Per the docs (nautilustrader.io/docs/latest/integrations/), the following crypto-relevant venues are marked **stable**, each supporting historical data requests, live data streaming, execution-state reconciliation, standard order submission/modification/cancellation:

**Centralized exchanges (CEX):**
- Binance (spot + futures)
- Coinbase
- Bybit
- OKX
- Kraken
- BitMEX
- Deribit (options + perpetuals)

**Decentralized exchanges (DEX):**
- dYdX
- Hyperliquid
- Derive
- Lighter

**Adjacent/data:** Databento and Tardis as historical/live crypto+traditional market data providers (useful for backtesting even on venues without a live-execution adapter); Polymarket (prediction markets — arguably alt-data-adjacent for crypto sentiment); plus Interactive Brokers, Betfair, AX Exchange for non-crypto asset classes (out of scope here).

This is a materially broader and more actively maintained crypto adapter set than most open-source trading frameworks — coverage spans the major CEXs (Binance/Coinbase/Bybit/OKX/Kraken) and the leading perp DEXs (dYdX/Hyperliquid), which is exactly the exchange surface a crypto alt-data strategy would need for both signal backtesting and eventual execution.

### License — LGPL-3.0, confirmed

Confirmed LGPL-3.0 (GNU Lesser General Public License v3) on the `develop` branch LICENSE file.

**Implications for combining with proprietary code:**
- LGPL-3.0 is specifically designed to allow proprietary ("Application") code to use an LGPL "Library" without forcing the proprietary code itself to be open-sourced — this is the standard "use as a dependency" case (`pip install nautilus_trader`, `import nautilus_trader`, write your own strategy/signal code on top).
- Requirements that DO apply: prominent notice that the Library is used and LGPL-covered; accompanying the LGPL/GPL license text; if you **modify nautilus_trader's own source** and distribute that modified version, the modifications must be released under LGPL (or GPL) terms.
- Practical read for this project: as long as `api.quiverquant.com` treats nautilus_trader as an unmodified (or upstream-contributed) dependency and keeps its own strategy code, alt-data pipeline, and signal-generation logic in separate modules/packages rather than editing nautilus_trader's internals, there is **no obligation to open-source the proprietary strategy/signal code**. This is the normal use pattern and the one the project should plan around. Only a concern if the plan is to fork-and-modify the engine itself rather than extend it via its plugin/strategy APIs.
- Contrast with the closest OpenFoundry candidate (`u485349-coder/OpenFoundry`), which is AGPL-3.0 — a much stricter copyleft that would trigger network-use disclosure obligations. Not a live concern since that repo isn't being adopted, but worth flagging if any AGPL-licensed component is considered later.

### Data requirements & custom alternative-data ingestion

- Nautilus's native data hierarchy runs from most to least granular: **L3 order book (market-by-order) → L2 (market-by-price) → L1 quote ticks → trade ticks → bars**. It has its own Arrow/Parquet-based catalog format (`ParquetDataCatalog`) for efficient large-dataset backtests, but the low-level `BacktestEngine` API also accepts **raw data in arbitrary original formats (CSV, binary, etc.)** loaded via `add_data()` / `add_data_iterator()`, including streaming/chunked loading for datasets larger than RAM.
- **Custom/alternative data is a first-class concept**, not a bolt-on: developers subclass the `Data` base class (implementing `ts_event`/`ts_init` for correct time-ordering against market data), optionally use the `@customdataclass` decorator to get serialization "for free," then `publish_data()` / `subscribe_data()` the custom type so strategies receive it through the same `on_data()` event handler used for market data. This means an on-chain whale-transfer feed, a social-sentiment score series, or any other `api.quiverquant.com`-produced signal can be timestamped and streamed into a Nautilus strategy **interleaved correctly with price/order-book events** — important for avoiding lookahead bias when backtesting a signal-driven strategy.
- Caveat: documentation depth for custom data is thinner than for native market data (the flagship example is an options Greeks feed, not an alt-data-style signal), so there will be a learning-curve / example-writing cost, but no architectural blocker.

### Backtesting capabilities

- Two API levels: high-level `BacktestNode` (config-object driven, meant for repeatable/production-style backtest runs — this is what you'd use for systematic re-qualification of a strategy) and low-level `BacktestEngine` (manual control, single run).
- **Fill/slippage realism:** with L2/L3 order-book data, fills are simulated by walking the actual book depth level-by-level; with L1/bar data, a configurable `FillModel` applies probabilistic slippage (`prob_slippage`), and there are 8 built-in fill models (e.g. `ThreeTierFillModel`, `SizeAwareFillModel`) for approximating market impact at different sophistication levels when full-depth data isn't available (a very realistic scenario for free/low-cost crypto data sources).
- **Fee/commission modeling** is handled via the accounting framework, with `CASH`, `MARGIN`, and `BETTING` account types — relevant for modeling crypto spot vs. margin/perp fee structures accurately.
- **Multi-asset/multi-venue:** a single backtest run supports multiple venues and multiple instruments simultaneously (docs cite a working example of "10 instruments, each with 1M bars"), which matters for a strategy that trades a basket of tokens based on aggregated alt-data signals rather than one pair.
- **Walk-forward / repeated testing:** no built-in named "walk-forward" or Monte Carlo feature, but the architecture directly supports it — `BacktestNode` accepts multiple `BacktestRunConfig` objects for batches of runs, and `BacktestEngine.reset()` preserves loaded data/instruments/venues while resetting trading state, which is the standard building block for rolling-window walk-forward loops and parameter sweeps. Actual walk-forward orchestration (rolling date windows, out-of-sample scoring) would need to be scripted on top — not a big lift, but not turnkey either.

### Maturity / maintenance signal

- **~24.4k GitHub stars, ~3.1k forks** — this is one of the largest open-source algo-trading frameworks by community size.
- **Release cadence:** actively maintained, roughly bi-weekly releases in 2026 (e.g. v1.225.0 Apr 6 → v1.226.0 Apr 29 → v1.227.0 May 18 → v1.228.0 Jun 8 → v1.229.0 Jun 25 → v1.230.0 Jun 29, 2026). Versioning is still pre-1.0-semver-stable in spirit (1.x "Beta" labels persist), so expect occasional breaking API changes between minor versions — pin versions and read changelogs before upgrading.
- Backed by a company (Nautech Systems) with a tiered commercial offering built on the same OSS core, which is a positive maintenance signal (funded incentive to keep the open core healthy) but also means the most advanced infra/support is paywalled.
- Active Discord and Telegram community; 35+ named GitHub contributors; extensive automated test suite plus supply-chain security tooling (SLSA Build Level 3, Sigstore) — signals of a mature engineering process rather than a hobby project.
- Available on PyPI (`pip install nautilus_trader`) for straightforward adoption.

---

## 3. Fit assessment

### nautilus_trader — strong fit, primary recommendation

nautilus_trader is a credible, production-grade candidate for the execution/backtesting engine layer of this project:

- **Strengths for this project specifically:** broad, actively-maintained crypto CEX+DEX adapter coverage (Binance/Coinbase/Bybit/OKX/Kraken + dYdX/Hyperliquid) covers essentially every venue a free-data crypto strategy would want to trade or backtest against; the custom-data framework is architecturally well-suited to piping in `api.quiverquant.com`'s alt-data signals (on-chain whale activity, sentiment, dev activity) alongside price data with correct event ordering; research/live parity reduces the risk that a strategy validated in backtest behaves differently once "continuously re-qualified" in production, which is explicitly a project goal.
- **License is workable:** LGPL-3.0 permits using it as a dependency from proprietary strategy code without an obligation to open-source the alt-data/signal logic, as long as the project doesn't fork-modify the engine internals directly.
- **Integration effort:** moderate. It's a real framework with its own conventions (Strategy/Actor classes, Data catalog, config objects) — expect a learning-curve investment (days, not hours) to get a first custom-data-driven strategy running in backtest, plus scripting work to build walk-forward/parameter-sweep orchestration on top of `BacktestEngine.reset()` / `BacktestNode`, since that isn't turnkey. No blocking gaps were found for the "validate a crypto investment strategy against alt-data signals" use case.
- **Risk to flag:** pre-1.0 versioning means API changes between releases; the bi-weekly release cadence is a maintenance-active positive but also means version pinning and changelog review discipline will be needed.

### Open Foundry (syzygyhack/open-foundry) — good fit, different role than assumed

Not a trading or strategy component — has zero finance-specific code. But it's a credible fit as the **ontology/data-integration layer**: a self-hostable, Apache-2.0-licensed graph/ontology platform with GraphQL+REST APIs that can model wallets, protocols, tokens, VCs, and exchanges as related entities, ingest the outputs of every free data collector into one coherent queryable model, and use its CEL action framework to fire alerts/triggers (e.g. "VC wallet X moved funds to exchange Y" → notify strategy layer). Requires building a custom crypto Domain Pack (not present out of the box) — real scoping work but not a blocker, and the AML domain pack that already exists is a useful reference pattern for the regulatory/compliance alt-data category. Sits upstream of nautilus_trader in the architecture: Open Foundry unifies and models the data, nautilus_trader consumes it as custom-data signals for backtesting/execution.
