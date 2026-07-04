# Research: "QuantHedgeFund" and "Crypto-Alpha-Scanner" GitHub Candidates

**Date:** 2026-07-02
**Scope:** Research-only. Evaluating two generically-named GitHub projects as potential strategy/signal-scanning components for a free, crypto-scoped "alternative data" aggregation base (QuiverQuant-style). Only crypto-relevant capabilities considered. No code was written or cloned.

**Bottom line up front:**
- **"QuantHedgeFund"** — No single well-known, canonical repo exists under this name. One small real repo was found (`Ashutosh0x/QuantHedgeFund`, 20 stars) but it is primarily an equities/IB backtesting stack with only incidental crypto data support, and it carries no open-source license. **Confidence this is "the" intended repo: LOW.** Two other repos surfaced by search engines under this name (`jarmni/QuantHedgeFund`, `Johnclinton95-coder/QuantHedgeFund`) **do not actually exist** (confirmed 404 via GitHub API) — they are almost certainly search-engine hallucinations or since-deleted spam. Do not trust those URLs.
- **"Crypto-Alpha-Scanner"** — One real, matching-name repo exists (`xCodeWraith/Crypto-Alpha-Scanner`, 47 stars) but it is not a scanning tool/codebase — it's a single n8n workflow JSON file plus a README, meant to be imported into the n8n automation platform. It has no source code to evaluate or integrate as a library. **Confidence this is "the" intended repo: LOW-MEDIUM** (it's the only real match, but likely not what's meant by "a scanner component").
- For both names, there is a suspicious proliferation of near-identical, zero-star, freshly-created (2026) repos with the same or near-identical descriptions across unrelated accounts — see "Naming pattern caution" sections below.
- **Recommended path:** use well-established, actively maintained open-source alternatives instead of either literal repo (see recommendations at the end of each section).

---

## 1. "QuantHedgeFund"

### Candidates found

| Repo | Stars | Forks | Last push | Language | License | Status |
|---|---|---|---|---|---|---|
| [Ashutosh0x/QuantHedgeFund](https://github.com/Ashutosh0x/QuantHedgeFund) | 20 | 12 | 2026-03-16 | Python (99.6%) | **None** (no LICENSE file — all rights reserved by default) | Real, active, small hobby-scale project |
| jarmni/QuantHedgeFund | — | — | — | — | — | **Does not exist** — GitHub API returns 404. Surfaced only in search snippets, not a real repo. |
| Johnclinton95-coder/QuantHedgeFund | — | — | — | — | — | **Does not exist** — GitHub API returns 404. Same pattern as above. |
| mfotous/QuantHedgeFund | 0 | 0 | 2026-05-03 | none detected | none | Real but empty/placeholder repo, no description, no code of substance |
| RogerDeng/QuantHedgeFund | 0 | 0 | 2026-02-21 | Python | — | Not investigated further — 0 stars, no description |

Search methods used: `github.com/search?q=QuantHedgeFund`, GitHub REST search API (`/search/repositories?q=QuantHedgeFund+in:name`), general web search for "QuantHedgeFund github", and variant terms ("quant-hedge-fund", "QuantitativeHedgeFund"). No repo literally named `quant-hedge-fund` or `QuantitativeHedgeFund` with meaningful activity was found.

### Deep dive: Ashutosh0x/QuantHedgeFund

- **Description:** "A Python-powered Quant Hedge Fund System with automated data ingestion, backtesting, and trade execution using MLflow, Luigi, Prefect, and Interactive Brokers"
- **Created:** 2025-12-30, **last pushed:** 2026-03-16 (roughly 3.5 months of activity, then apparently stalled — over 3 months stale as of this report)
- **License:** No LICENSE file present in the repo (GitHub API reports `license: null`). This means the code is **not** open source by default (all rights reserved to the author) — a real blocker for building on it in a "free/open" project without contacting the author.
- **Architecture (per README):**
  - Data layer ("QS Connect"): bulk price downloads, DuckDB storage, Parquet caching, Zipline bundler, rate-limited API access, and a **Twelve Data WebSocket feed described as covering "stocks, forex, and crypto"** — this is the only crypto touchpoint.
  - Research layer ("QS Research"): momentum factor computation, universe screening, backtesting with parameter sweeps, MLflow experiment tracking, XGBoost ML, LLM-based regime analysis (Grok/Llama 3 70B).
  - Execution layer ("Omega"): built specifically around **Interactive Brokers** — IB has only limited/indirect crypto execution support (via Paxos, and only for a few coins in the US), so live crypto trading through this stack would be constrained.
  - Orchestration (Luigi/Prefect) and a Streamlit monitoring dashboard.
- **Crypto relevance verdict:** Weak/incidental. Crypto is one bullet point in a data-feed layer bolted onto what is fundamentally an equities/forex-oriented, IB-centric backtesting and execution stack. Portfolio construction, factor models, and risk guardrails are present conceptually and could inspire architecture, but the crypto data plumbing and execution path are not built out.
- **Maintenance/quality signal:** Small (20 stars/12 forks), single-author-looking project, ~3 months of activity then quiet, no license, no tests visible in search snippets, no CI badge mentioned. This reads as a solo portfolio/demo project, not a maintained framework.

### Naming pattern caution

Two of the four "QuantHedgeFund" hits returned by general web search (`jarmni/...`, `Johnclinton95-coder/...`) do not correspond to real GitHub repositories — the GitHub REST API returns a clean 404 for both, and fetching the GitHub web page for `jarmni/QuantHedgeFund` also 404s. Treat any AI-generated search summary of these two as unreliable; **do not use these URLs**. The remaining zero-star, zero-description entries (`mfotous`, `RogerDeng`) look like placeholder/abandoned repos, not usable software.

### Recommendation: do not adopt Ashutosh0x/QuantHedgeFund as the strategy framework

Given the missing license, thin/incidental crypto support, IB-centric execution model, and short activity window, this repo is not a good foundation for a crypto-only, free/open aggregation project. Instead, consider these well-established, verifiably active, crypto-relevant alternatives that better fill the "quant hedge-fund style multi-strategy framework" role:

| Repo | Stars | License | Last push | Why it fits |
|---|---|---|---|---|
| [nautechsystems/nautilus_trader](https://github.com/nautechsystems/nautilus_trader) | 24,375 | LGPL-3.0 | 2026-07-02 (same-day, very active) | Production-grade, event-driven, Rust-core/Python-strategy algo trading platform. Multi-asset including crypto CEX/DEX, backtesting + live trading with shared engine semantics, portfolio/risk components — closest fit to a "hedge fund" style multi-strategy engine with real crypto support. |
| [freqtrade/freqtrade](https://github.com/freqtrade/freqtrade) | 52,007 | GPL-3.0 | 2026-07-02 (same-day, very active) | Crypto-native (not multi-asset), huge community, backtesting, hyperparameter optimization, FreqAI adaptive ML module, multi-exchange. More "trading bot" than "hedge fund," but extremely well maintained and a strong base for strategy/signal research. |
| [jesse-ai/jesse](https://github.com/jesse-ai/jesse) | 8,132 | MIT | 2026-07-02 (same-day, active) | Crypto-focused backtesting/live-trading framework, permissive MIT license, simpler API surface than Nautilus if a lighter-weight base is preferred. |

Of these, **NautilusTrader** is the closest conceptual match to "hedge-fund style" (portfolio/risk/multi-strategy architecture) while still being crypto-capable and permissively enough licensed (LGPL-3.0) for a free/open project; **freqtrade** is the safer choice if the priority is crypto-only breadth, community size, and proven longevity.

---

## 2. "Crypto-Alpha-Scanner"

### Candidates found

| Repo | Stars | Forks | Last push | Language | License | Notes |
|---|---|---|---|---|---|---|
| [xCodeWraith/Crypto-Alpha-Scanner](https://github.com/xCodeWraith/Crypto-Alpha-Scanner) | 47 | 14 | 2026-01-04 (single commit, created same day) | JSON (n8n workflow) | MIT (per README footer; not machine-detected by GitHub) | **Only real, matching-name repo of substance.** Not a codebase — see deep dive below. |
| alfadeepmode/Crypto-Alpha-Scanner | 1 | — | 2026-06-01 | Python | — | "n8n → AutoGen Multi-Agent: On-chain alpha scanner with AI analysis (GPT-4o)" — appears to be a derivative/expansion of the xCodeWraith concept. Not investigated in depth; 1 star. |
| AYdeveloper/Crypto-Alpha-Scanner | 0 | 0 | 2026-07-02 | none | none | Empty/placeholder, same description text as xCodeWraith's — clone pattern. |
| jellingham24-dev/ALPHASCANNER, schoolsept2020-lgtm/alphabot, HoneyBee66661/alpha-scanner, AlphaGenesisAIDev/crypto-scanner-dashboard, Full-Access-Video/crypto-alpha-scanner, c114147101-pixel/crypto-alpha-scanner, prottushjdebnath-wq/crypto-alpha-scanner, Aqua-4/alpha_crypto_scanner | all 0 | — | scattered through 2026 | mixed | All zero-star, no substantive description or evidence of real functioning code. Not viable candidates. |

Search methods used: `github.com/search?q=Crypto-Alpha-Scanner`, GitHub REST search API (`/search/repositories?q=crypto+alpha+scanner`), general web search for "Crypto Alpha Scanner github" and variants ("crypto-alpha-scanner", "CryptoAlphaScanner", "alpha scanner crypto").

### Deep dive: xCodeWraith/Crypto-Alpha-Scanner

- **Repo contents:** literally two files — `Crypto Alpha Scanner.json` (an n8n workflow export) and `README.md`. There is no application source code (no Python/JS/etc.) to read, extend, or run outside of n8n.
- **What it claims to do (per README):** monitor mempool/on-chain data in real time (rather than relying on CoinGecko-type APIs) to flag whale transactions, new liquidity pool creation ("sniping" potential), and early rug-pull/dump warning signs, then push Telegram/Discord alerts. Optional GPT-based transaction analysis and honeypot/contract-safety checks.
- **Dependencies:** Alchemy/Infura/QuickNode (RPC), Etherscan API, CoinGecko/DexScreener, optionally GoPlus/TokenSniffer, Telegram/Discord webhooks — i.e., it's a thin orchestration layer over several third-party paid/rate-limited APIs, not a self-contained scanning engine.
- **Maintenance signal:** single commit, created and pushed same day (2026-01-04), no subsequent updates, no issues/PRs visible, no CI. 47 stars/14 forks is a moderate amount of attention for a single-commit repo, which itself is a mild red flag (star count out of proportion to actual content/activity — consistent with promotional/tutorial traffic rather than organic engineering adoption).
- **Crypto relevance:** High in concept (on-chain whale/rug/liquidity monitoring is exactly "alpha scanning"), but zero reusable code — you'd be re-implementing the whole thing in n8n's proprietary workflow format, or reverse-engineering the JSON to extract logic, either of which is more integration cost than it saves for a real backend project.

### Naming pattern caution

There is a cluster of extremely similar, near-simultaneously created repos across unrelated GitHub accounts in 2026 all named some variant of "Crypto Alpha Scanner" / "crypto-alpha-scanner," most with 0 stars and either an empty or copy-pasted description ("Analyze on-chain movements instantly to capture unseen crypto opportunities..."). This strongly suggests the xCodeWraith repo is a template being copied by course participants, tutorial followers, or automated repo-generation activity, rather than there being one canonical, actively-developed "Crypto Alpha Scanner" project. Treat all of them as low-trust for direct reuse. (Note also that on-chain "alpha scanner" workflow templates of this shape are a common vector for credential/RPC-key phishing in crypto tooling — if this repo or its clones are ever actually run, review the workflow JSON carefully before supplying any API keys.)

### Recommendation: do not adopt xCodeWraith/Crypto-Alpha-Scanner as the scanning component

No source code to build on, single-commit/low-maintenance signal, and a dependency chain of third-party paid APIs make it unsuitable as a foundation. Instead, consider:

| Repo | Stars | License | Last push | Why it fits |
|---|---|---|---|---|
| [CryptoSignal/crypto-signal](https://github.com/CryptoSignal/crypto-signal) | 5,592 | MIT | 2024-07-07 (**stale — no commits in ~2 years, but not archived**) | Purpose-built crypto TA signal scanner: RSI, MACD, Ichimoku, MFI, OBV, VWAP, moving averages across 500+ coins on Binance/Coinbase/Gemini, with Telegram/Discord/Slack/SMS/email alerting. Directly matches "technical-indicator alpha scanner." Caveat: development has stalled, so expect to fork and update dependencies rather than use as-is. |
| [freqtrade/freqtrade](https://github.com/freqtrade/freqtrade) | 52,007 | GPL-3.0 | 2026-07-02 (very active) | Not a pure scanner, but its whitelist/pairlist system continuously screens large numbers of crypto pairs against configurable technical-indicator strategies and FreqAI models — can be run in "dry-run"/signal-only mode as a de facto multi-pair alpha scanner, with the benefit of a huge, current, well-tested codebase. |
| [Superalgos/Superalgos](https://github.com/Superalgos/Superalgos) | 5,556 | Apache-2.0 | 2026-07-02 (very active) | Visual crypto trading platform with an integrated "Data Mining" module for indicator/pattern-based screening plus charting and backtesting; actively maintained with a live community since 2020. Apache-2.0 is a clean permissive license for reuse. |

If the goal is closest conceptual match to "alpha scanner" (indicator-driven signal generation + alerting), **CryptoSignal/crypto-signal** is the best shape but needs a maintenance-freshness fork; if active maintenance matters more than exact shape, **freqtrade** or **Superalgos** are safer bets.

---

## Summary of confidence levels

| Name searched | Confident single-repo match? | Best real candidate | Verdict |
|---|---|---|---|
| QuantHedgeFund | **No** | Ashutosh0x/QuantHedgeFund (20 stars) | Real but weak crypto relevance, no license, small/stalled. Use NautilusTrader or freqtrade instead. |
| Crypto-Alpha-Scanner | **No** | xCodeWraith/Crypto-Alpha-Scanner (47 stars) | Real but is an n8n workflow file, not a codebase. Use CryptoSignal/crypto-signal, freqtrade, or Superalgos instead. |

Both target names appear to be either non-canonical/generic phrases with no single well-known project behind them, or in the QuantHedgeFund case, partly fabricated by search-result summarization (two of four hits do not exist as real repos). Recommend proceeding with the established alternatives listed above rather than either literal named repo.
