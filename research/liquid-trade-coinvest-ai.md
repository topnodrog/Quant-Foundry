# Research: liquid.trade and coinvest.ai as an Execution/Aggregation Layer

**Date:** 2026-07-02
**Scope:** Crypto-relevant aspects only, evaluated as a possible execution/portfolio layer sitting on top of free data sources and open-source backtesting/quant frameworks (e.g. nautilus_trader).

## Key finding up front: these are the same company, not two platforms

`coinvest.ai` is **not** an independent company. It 301-redirects to `https://www.liquid.trade/coinvest`, and news coverage confirms "Co-Invest" is a product launched by Liquid (the liquid.trade company) in May 2026. So this report is really "Liquid, the platform" + "Co-Invest, Liquid's AI/agent-trading product line built on the same account/backend." There is no separate due-diligence needed for a second company — but Co-Invest does add a genuinely distinct integration surface (an MCP/agent trading interface) worth evaluating on its own.

## Naming collisions — read this before searching further on your own

Both names are heavily reused in crypto, and mixing them up would produce wrong conclusions:

- **"Liquid" the subject of this report** = `liquid.trade`, founded 2025 by Franklyn Wang (ex-Two Sigma), a 24/7 multi-asset leveraged trading app. This is the entity behind `coinvest.ai`/Co-Invest.
- **NOT** Liquid.com / "Liquid Global" (formerly QUOINE) — a Japanese exchange that was hacked for ~$94-97M in August 2021 (and suffered a DNS-hijack/phishing breach in Nov 2020), later absorbed into FTX and then wound down after FTX's collapse. Its API docs live at `developers.liquid.com` and are unrelated to liquid.trade.
- **NOT** "Liquid Brokers" / "Liquid Markets" / "Liquidfx.io" / "Liquidusfxtrade" — unrelated FX/CFD brokers with their own (mixed-to-poor) Trustpilot/WikiFX review histories.
- **NOT** "Liquid MarketPlace" — an NFT marketplace co-founded by Logan Paul, currently facing Ontario Securities Commission fraud allegations against its executives.
- **"Coinvest" the subject of this report** = `coinvest.ai` → redirects to Liquid's Co-Invest product.
- **NOT** the older "Coinvest" blockchain/tokenized-investment project listed on Republic (a pre-2020-era crowdfunded blockchain startup, unrelated, could not confirm current status — fetch was blocked).
- **NOT** `coinvest.pro` / `coinvestus.com` — flagged by New Zealand's Financial Markets Authority and by Broker Watch Dog as fraud-linked imposter investment sites (fake platform, no license, deceptive funnels, withdrawal blocks). Do not confuse with `coinvest.ai`.

---

## 1. liquid.trade

### What it is
Liquid is a venture-backed startup (launched publicly ~August 2025) building a single 24/7 trading app that spans crypto, US/international equities, commodities, FX, Polymarket prediction-market positions, and pre-IPO private-company secondaries (e.g. exposure tied to OpenAI, Anthropic, SpaceX). It started as an aggregator for crypto perpetual futures and has since expanded into other asset classes. It markets itself around high leverage ("$100 controls a $20,000 position," up to 100-200x depending on jurisdiction/asset) and instant, lock-up-free entry/exit.

**Team:** Founded by Franklyn Wang, a Harvard graduate and former quantitative researcher at Two Sigma (described in some coverage as "former Chief of AI, Two Sigma" — titles vary by source). The team is described as drawing from Two Sigma, Bloomberg, D.E. Shaw, and Gauntlet.

**Funding:** Seed round of $7.6M led by Paradigm (2025), followed by an $18M Series A in April 2026 co-led by Neo and Left Lane Capital, with participation from General Catalyst, Haun Ventures, K5 Global, SV Angel, AntiFund, and Sunflower Capital. Total disclosed funding ≈ $25.6M. As of the Series A, Liquid reported >$3B in cumulative trading volume and ~40,000 users.

**Legal entity/incorporation:** Not disclosed in any marketing or press material found. No jurisdiction, entity name, or registration number surfaced in searches — this is itself worth flagging (see Trust/Status section).

### Crypto product features
- **Trading:** Primarily crypto perpetual futures (derivatives), plus spot-like exposure via routed venues. Long and short positions with leverage up to 100-200x depending on asset/jurisdiction.
- **Execution model:** Liquid does not run its own exchange/order book for these assets. It is explicitly **non-custodial** and **routes orders to third-party venues**: Hyperliquid (perps and spot), Lighter, and Ostium (crypto, indices, FX, stocks, commodities). Liquid is best understood as an aggregation/UX/leverage layer in front of these DEXs, not a custodial exchange itself.
- **Portfolio/index products:** No dedicated index or basket product found; it's positioned as single-position leveraged trading across many markets from one balance/UI, not a managed-portfolio product.
- **Automated strategies / copy trading:** No native copy-trading found. However, the **Co-Invest** product line (below) is explicitly an automation/agent surface.
- **Staking/yield:** Liquid docs mention "Vaults" and "HLP" (Hyperliquid's liquidity-provider vault) as yield-bearing products, i.e., liquidity-provision yield inherited from Hyperliquid rather than a Liquid-native yield product.
- **Assets:** BTC, ETH, SOL, HYPE and other Hyperliquid-listed assets for crypto; plus non-crypto markets (stocks, FX, commodities, prediction markets, pre-IPO) through Ostium/other venues.
- **KYC:** Liquid's own FAQ states it "doesn't require KYC to trade" and frames this as a privacy/security feature ("nothing to leak"). Funding methods include Apple Pay, PayPal, Venmo, cards, bank transfer, and crypto — several of which (card, PayPal, bank) would typically require some identity/payment verification even if Liquid itself doesn't collect KYC directly.

### API availability
Liquid exposes a documented developer surface at **`sdk.tryliquid.xyz`** (API/SDK docs) and **`docs.tryliquid.xyz`** (product docs), distinct from the unrelated `developers.liquid.com` (Liquid.com/QUOINE's old API, not this company).

- Stated interfaces: **REST API**, a **Python SDK** (`pip install liquidtrading-python`), and an **MCP Server**.
- The publicly crawlable documentation is thin: the marketing/docs pages describe non-custodial architecture, funding methods, fees, leverage, TWAP orders, funding rates, liquidations, and a referral/points system — but do **not** publicly expose endpoint-level REST reference, authentication scheme details, rate limits, or pricing tiers in the pages we could fetch. This may be gated behind account creation/API-key issuance, or simply thin/new documentation (Co-Invest itself only shipped ~May 2026).
- No evidence of a free, no-signup, read-only market-data API. Given execution routes through Hyperliquid/Ostium, it's plausible (but unconfirmed) that raw market data could instead be sourced directly from those venues' own public APIs rather than through Liquid.
- Auth: docs reference OAuth support for the MCP/agent integration; specifics not confirmed from public pages.

### Integration feasibility as an execution/aggregation layer
Liquid is explicitly positioning itself for this exact use case via **Co-Invest Computer** (see below), which is the more relevant integration point than the base consumer app. Feasibility notes:
- **Pro:** Non-custodial + programmatic order execution + configurable risk controls + a simulation mode are a good fit for a strategy-execution layer.
- **Pro:** Broad crypto asset coverage inherited from Hyperliquid, plus optional access to non-crypto markets if the project ever wants to expand scope.
- **Con/Blocker:** Public API reference material is sparse; you'd likely need to sign up and pull real docs/credentials to know true rate limits, latency, and order-type coverage before committing engineering time.
- **Con/Blocker:** Since execution is routed through Hyperliquid/Lighter/Ostium, a project could potentially integrate with those venues' own (better-documented, more established) APIs directly and skip Liquid/Co-Invest as an intermediary — worth comparing before adopting Liquid as the aggregation layer.
- **Con/Blocker:** No disclosed legal entity or regulatory registration; leverage up to 100-200x offered to US retail users without broker/exchange registration is a legally aggressive stance (see red flags below) — a risk to weigh before routing real capital through it.

### Trust/status signals
- **Age:** Young — public launch ~August 2025, Co-Invest ~May 2026. Under one year old as of this report.
- **Funding:** Legitimate, name-brand crypto VCs (Paradigm, General Catalyst, Haun Ventures) — a positive signal of institutional diligence having been done at some level.
- **Regulatory positioning — red flag:** Liquid's stated legal justification for not registering as a broker/exchange leans on "recent SEC/CFTC guidance, including the CFTC's no-action letter for Phantom." We verified this letter (CFTC Staff Letter 26-09, issued March 17, 2026): it is a no-action position issued **specifically to Phantom Technologies Inc.**, conditioned on ten specific compliance obligations Phantom agreed to (disclosures, fee transparency, routing only to CFTC-registered DCMs/FCMs/IBs, etc.). No-action letters are addressed to and legally binding only for their named recipient — they are not blanket industry relief. Liquid citing this as a general legal basis for its own (much more aggressive: up to 200x leverage, explicitly "no KYC") product is a stretch, and Liquid was not itself a party to that letter. This is a meaningful legal/regulatory red flag for anyone considering routing real funds through it.
- **Reviews:** Very limited public review history — only ~2 Trustpilot reviews found for `www.liquid.trade` at time of research, both mildly positive/neutral. Not enough signal to assess reputation either way. (Note: many negative reviews found in search actually belong to unrelated "Liquid Brokers"/"Liquid Markets" FX brokers — see naming collisions above; don't let those poison the read on liquid.trade itself.)
- **Security incidents:** No security incidents or breaches found specifically tied to liquid.trade or Co-Invest. (The well-documented $94-97M hack and DNS-hijack breach both belong to the unrelated Liquid.com/QUOINE exchange — see naming collisions.)
- **Transparency gap:** Could not find a disclosed legal entity name, incorporation jurisdiction, or any licensing/registration on the marketing pages accessible to us. For a platform offering high-leverage derivatives to US persons, this is a notable transparency gap worth confirming directly (in ToS/account signup flow) before connecting capital.

---

## 2. coinvest.ai / Co-Invest (Liquid's AI-agent trading product)

### What it is, concretely
`coinvest.ai` is Liquid's marketing domain for **Co-Invest**, an AI-agent trading integration launched May 2026, with two related surfaces:
1. **Co-Invest (chat app):** An app inside ChatGPT and Claude (as a custom connector) that lets a user fund an account, ask the AI to analyze markets, and execute trades without leaving the chat window. Every trade requires an explicit user confirmation tap — described by Liquid as both a UX choice and a fraud-prevention measure. The connector's server URL is `coinvest.liquid.trade`.
2. **Co-Invest Computer ("Automated Trading MCP"):** A more autonomous surface, described as an MCP server that lets an agent/harness "research markets, monitor entries, and execute trades." It supports configurable **risk controls** — max notional, max leverage, mandatory stop-loss, optional symbol allowlists, daily order caps, and order expiry — plus a **simulation/staged-orders mode** to dry-run an agent loop against live market data before flipping to live execution, carrying the same strategy/risk config forward. Publicly stated pricing: Co-Invest Computer itself is free to use; executed trades pay Liquid's standard trading fees; LLM token/model usage is billed separately by whichever model provider the MCP client uses.

This is the same company, same backend, same underlying venues (Hyperliquid, Lighter, Ostium) as liquid.trade — Co-Invest is not a separate liquidity source or a separate legal/regulatory posture.

### Crypto product features
Same asset/venue coverage as liquid.trade (crypto, equities, FX, commodities, Polymarket, pre-IPO across 500+ markets), just accessed through an AI-agent-native interface instead of (or in addition to) the standard app.

### API availability
- Integration methods advertised: **CLI, MCP SDK, or AI SDK**, with OAuth handled by the service.
- This is the most directly relevant piece for a strategy-execution use case: Co-Invest Computer's risk-control primitives (max notional/leverage, stop-loss enforcement, symbol allowlist, daily order caps, expiry, simulation mode) map closely onto what a backtested-strategy-to-live-execution pipeline needs.
- As with the base Liquid API, we could not pull a public endpoint-level reference (parameter schemas, exact rate limits) from crawlable docs — likely requires signing up / installing the SDK to see the real contract.

### Integration feasibility
Of the two, **Co-Invest Computer is the more purpose-built fit** for this project's stated goal (an execution layer fed by external signals/backtests). It's explicitly designed for exactly this "agent generates a strategy, executes with guardrails, can be dry-run first" workflow, which is unusually well-aligned. The blockers are the same ones that apply to Liquid generally: thin public API documentation, unclear rate limits, and the unresolved regulatory-posture question, since Co-Invest execution is the same non-custodial routing through Hyperliquid/Lighter/Ostium under the same no-action-letter rationale discussed above.

### Trust/status signals
Same company, same age (younger still — Co-Invest is ~2 months old at time of writing), same funding backers, same regulatory red flag as liquid.trade. No incidents specific to Co-Invest found. One additional consideration: routing an autonomous/algorithmic agent with real order-placement authority through a very new, non-custodial, leverage-heavy platform compounds operational risk (bugs in either Liquid's routing layer or in your own agent) beyond what a human-confirmed trade already carries — worth extra caution given how new this specific product is (weeks old, not months).

---

## Verdict: fitness as an execution/aggregation layer

| Dimension | liquid.trade (base app) | coinvest.ai / Co-Invest Computer |
|---|---|---|
| Purpose-built for automated execution | No (human-confirmed chat trading) | Yes — explicit risk controls + simulation mode |
| Public API documentation depth | Thin | Thin (same underlying platform) |
| Custody model | Non-custodial (pro) | Non-custodial (pro) |
| Regulatory clarity | Weak — leans on a no-action letter issued to a different company (Phantom) | Same weakness, inherited |
| Company/product maturity | ~1 year | ~2 months |
| KYC | None required (per Liquid FAQ) | Same |
| Underlying liquidity | Hyperliquid, Lighter, Ostium (third-party) | Same |

**Bottom line:** `coinvest.ai` is not an independent option — it's Liquid's own agent/MCP-native execution surface, and for a project that wants a strategy-to-execution pipeline, **Co-Invest Computer is the more relevant integration point than the base liquid.trade app**, largely because of its built-in risk-control and simulation-mode primitives. However, before wiring in real capital, this project should independently verify (directly from Liquid, not from marketing pages) their actual API rate limits/auth model, and separately should weigh whether it's simpler and lower-risk to integrate directly with the underlying venues (Hyperliquid, in particular, has a mature, well-documented, widely-used Python SDK) rather than going through Liquid/Co-Invest as a middle layer.

### Red flags to weigh before connecting real funds
1. **Regulatory rationale is legally thin.** Liquid's "we don't need to register as a broker/exchange" position leans on a no-action letter (CFTC 26-09) issued specifically to Phantom Technologies under ten conditions Phantom agreed to — not a general industry exemption, and not a letter issued to Liquid.
2. **Very young company and product.** Liquid: ~1 year old. Co-Invest Computer: ~2 months old at time of research. Limited operating history under stress (e.g., a sharp market move, an exchange outage at Hyperliquid) to point to.
3. **No disclosed legal entity, jurisdiction, or license** found in any public material reviewed. Confirm directly in ToS before depositing funds.
4. **High leverage (up to 100-200x) + no KYC** is a combination that's convenient but also exactly the profile regulators tend to scrutinize; if the regulatory footing shifts, product availability/withdrawals could be affected with little notice.
5. **Non-custodial routing to third-party DEXs (Hyperliquid/Lighter/Ostium)** means Liquid is itself a dependency layered on top of other dependencies — an outage, exploit, or listing change at any of those venues affects Liquid/Co-Invest users too.
6. **Thin public developer docs** mean real integration terms (rate limits, exact auth flow, fee schedule for API users) are unknown until you actually sign up — can't fully scope integration effort from outside.
7. **Naming collisions are a practical risk in their own right**: it is very easy to accidentally read reviews/incident reports about Liquid.com (QUOINE, hacked for ~$95M), "Liquid Brokers," or `coinvest.pro` (an FMA-flagged scam site) and misattribute them to liquid.trade/coinvest.ai. Always double check the exact domain when researching further.

### Sources
- [Liquid — Trade Like The 1%](https://www.liquid.trade/)
- [Liquid Co-Invest — Trade in Claude, ChatGPT, and iMessage](https://www.liquid.trade/coinvest)
- [Liquid Co-Invest Computer — Automated Trading MCP](https://www.liquid.trade/coinvest-computer)
- [Liquid launches Co-Invest app, bringing AI-powered live trade execution into ChatGPT and Claude | The Block](https://www.theblock.co/post/402496/liquid-launches-co-invest)
- [Paradigm-backed Liquid raises $18 million in new funding to expand its 24/7 multi-asset trading platform | The Block](https://www.theblock.co/post/398271/paradigm-liquid-18-million-new-funding-trading-platform)
- [Exchange startup Liquid raises $18 million Series A for leveraged trading on stocks, crypto, commodities, prediction markets, and private secondaries | Fortune](https://fortune.com/2026/04/28/liquid-18-million-leveraged-trading/)
- [24/7 Trading Platform, Liquid, Closes $18 Million Funding Round (PRNewswire)](https://www.prnewswire.com/news-releases/247-trading-platform-liquid-closes-18-million-funding-round-302754621.html)
- [Liquid launches Co-Invest app for live trading inside ChatGPT and Claude — Cryptobriefing](https://cryptobriefing.com/liquid-co-invest-app-chatgpt-claude-trading/)
- [Understanding Co-Invest: A New Era of AI-Driven Trading — ValueTheMarkets](https://www.valuethemarkets.com/cryptocurrency/news/understanding-co-invest-a-new-era-of-ai-driven-trading)
- [Co-Invest - MCP | Smithery](https://smithery.ai/servers/coinvest/coinvest) (listing found, page itself returned 403)
- [Liquid API/SDK docs](https://sdk.tryliquid.xyz/)
- [Liquid product docs](https://docs.tryliquid.xyz/)
- [liquidtrading-python on PyPI](https://pypi.org/project/liquidtrading-python) (existence confirmed via search; page fetch failed)
- [CFTC Staff Issues No-Action Position to Self-Custodial Crypto Asset Wallet Software Provider (CFTC press release re: Phantom)](https://www.cftc.gov/PressRoom/PressReleases/9197-26)
- [CFTC Letter No. 26-09, March 17, 2026](https://www.cftc.gov/csl/26-09/download)
- [Phantom wins CFTC no-action relief — CoinDesk](https://www.coindesk.com/policy/2026/03/17/phantom-wins-cftc-no-action-relief-clearing-path-for-crypto-wallet-access-to-regulated-derivatives-markets)
- [Liquid Reviews | Trustpilot (www.liquid.trade)](https://www.trustpilot.com/review/www.liquid.trade)
- [Liquid cryptocurrency exchange loses over $90 million following hack — BleepingComputer](https://www.bleepingcomputer.com/news/security/liquid-cryptocurency-exchange-loses-over-90-million-following-hack/) (unrelated Liquid.com/QUOINE — see naming collisions)
- [OSC accuses Liquid MarketPlace of fraud — BetaKit](https://betakit.com/osc-accuses-liquid-marketplace-of-fraud-and-pursues-action-against-startup-top-execs/) (unrelated entity — see naming collisions)
- [Coinvest.pro Review: Is It a Scam or Legit? — Broker Watch Dog](https://www.brokerwatchdog.com/coinvest-pro-review-is-it-a-scam-or-legit/) (unrelated scam domain — see naming collisions)
- [Coinvest — Republic](https://republic.com/coinvest) (older, unrelated Coinvest project; fetch blocked, listed for completeness)
